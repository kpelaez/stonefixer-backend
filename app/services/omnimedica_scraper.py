# app/services/omnimedica_scraper.py
"""
Scraper Playwright para Omnimedica Stock.

Selectores y estructura validados contra HTML real (2026-06-08):

Login (en http://IP_SERVIDOR/):
  - Usuario:  input[name="Login1$UserName"]
  - Password: input[name="Login1$Password"]
  - Submit:   input[name="Login1$LoginButton"]

PageStockGrid.aspx (grilla principal):
  - Buscador: input[name="ctl00$ContentPlaceHolder1$TextBox_Search"]
  - Filas:    tr.grid_row, tr.grid_alt_row
  - Columnas validadas (9 celdas):
      [0] vacío (botón detalle)
      [1] cant. total
      [2] disponible
      [3] KIT
      [4] reservado
      [5] código/referencia
      [6] vacío
      [7] empresa
      [8] descripción
  - Paginación: links <a href="javascript:__doPostBack(...,'Page$N')">

PageStockGridDetalle.aspx (series individuales):
  - URL: misma IP + /PageStockGridDetalle.aspx (sin params, postback)
  - Filas: tr.grid_row, tr.grid_alt_row
  - Columnas validadas (9 celdas):
      [0] vacío
      [1] vacío
      [2] fecha ingreso
      [3] usuario
      [4] estado (ALTA | KIT(N))
      [5] lote
      [6] serie
      [7] vencimiento (dd/MM/yyyy)
      [8] depósito

Flujo crítico:
  - Entrar siempre por redir.omnimedica.com.ar → click 'CONTINUAR MANUALMENTE'
  - El login está en la página resultante (IP real), NO en /Login.aspx separado
  - Al volver del detalle el filtro se pierde → reconstruir búsqueda por producto
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.config import settings

logger = logging.getLogger(__name__)

_REDIR_URL  = "http://redir.omnimedica.com.ar"
_DELAY_MS   = 1_500
_TIMEOUT_MS = 30_000

_SEL_SEARCH = 'input[name="ctl00$ContentPlaceHolder1$TextBox_Search"]'
_SEL_FILAS  = "tr.grid_row, tr.grid_alt_row"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class OmnimedicaSerie:
    """Una serie individual extraída del detalle de producto."""
    codigo: str
    descripcion: str
    empresa: str
    serie: str
    lote: str
    vencimiento: str
    deposito: str
    estado_sistema: str          # "alta" | "kit"
    en_transito: bool = False
    kit_numero: Optional[str] = None


@dataclass
class ProductoResumen:
    """Fila de la grilla principal — un producto con cantidades."""
    codigo: str
    descripcion: str
    empresa: str
    cant_total: int
    cant_disponible: int
    cant_kit: int
    cant_reservado: int
    fila_index: int    # índice 0-based en la grilla (para el click del ImageButton)
    pagina: int        # número de página donde está este producto


@dataclass
class ScrapingResult:
    proveedor: str
    series: list[OmnimedicaSerie] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def exitoso(self) -> bool:
        return self.error is None


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class OmnimedicaScraper:
    """
    Scraper para el portal Omnimedica Stock.

    Uso:
        async with OmnimedicaScraper() as scraper:
            result = await scraper.extraer_stock("ARGENTINA MEDICAL PRODUCTS SRL")
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._base_url: Optional[str] = None

    async def __aenter__(self) -> "OmnimedicaScraper":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            ignore_https_errors=True,
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    async def extraer_stock(self, proveedor: str) -> ScrapingResult:
        """
        Entry point: redir → login → listado con paginación → detalle por producto.
        """
        result = ScrapingResult(proveedor=proveedor)
        page = await self._context.new_page()

        try:
            await self._redir_y_login(page)
            productos = await self._listar_todos_los_productos(page, proveedor)

            logger.info(
                f"[Omnimedica] '{proveedor}': {len(productos)} productos encontrados"
            )

            for producto in productos:
                series = await self._extraer_series_producto(page, producto, proveedor)
                result.series.extend(series)
                logger.debug(
                    f"[Omnimedica] Código '{producto.codigo}': {len(series)} series"
                )
                await self._delay()

            logger.info(
                f"[Omnimedica] Scraping completo: {len(result.series)} series totales"
            )

        except Exception as exc:
            logger.exception(f"[Omnimedica] Error en scraping de '{proveedor}'")
            result.error = str(exc)
        finally:
            await page.close()

        return result

    # ------------------------------------------------------------------
    # Redir + Login (flujo validado)
    # ------------------------------------------------------------------

    async def _redir_y_login(self, page: Page) -> None:
        """
        Flujo completo de acceso validado contra el sistema real:
          1. redir.omnimedica.com.ar → pantalla de selección de servidor
          2. Click en 'CONTINUAR MANUALMENTE' (o esperar auto-redir)
          3. Login en la IP resultante con selectores exactos
        """
        logger.debug(f"[Omnimedica] Iniciando desde {_REDIR_URL}")
        await page.goto(_REDIR_URL, wait_until="domcontentloaded", timeout=_TIMEOUT_MS)
        await asyncio.sleep(2)

        btn = await page.query_selector("text=CONTINUAR MANUALMENTE")
        if btn:
            await btn.click()
            await page.wait_for_load_state("networkidle", timeout=_TIMEOUT_MS)
            await asyncio.sleep(2)
        else:
            logger.warning("[Omnimedica] Botón 'CONTINUAR MANUALMENTE' no encontrado, esperando...")
            await asyncio.sleep(5)

        # Capturar IP del servidor activo
        parsed = urlparse(page.url)
        self._base_url = f"{parsed.scheme}://{parsed.netloc}"
        logger.info(f"[Omnimedica] Servidor activo: {self._base_url}")

        # Login con selectores exactos validados
        await page.fill('input[name="Login1$UserName"]', settings.OMNI_USER)
        await page.fill('input[name="Login1$Password"]', settings.OMNI_PASSWORD)
        await page.click('input[name="Login1$LoginButton"]')
        await page.wait_for_load_state("networkidle", timeout=_TIMEOUT_MS)
        await asyncio.sleep(1)

        # Si el botón de login sigue visible → credenciales incorrectas
        if await page.query_selector('input[name="Login1$LoginButton"]'):
            raise RuntimeError(
                "Login en Omnimedica fallido. "
                "Verificar OMNI_USER y OMNI_PASSWORD en .env"
            )

        logger.debug("[Omnimedica] Login OK")

    # ------------------------------------------------------------------
    # Listado de productos con paginación
    # ------------------------------------------------------------------

    async def _listar_todos_los_productos(
        self, page: Page, proveedor: str
    ) -> list[ProductoResumen]:
        """Busca el proveedor y extrae todos los productos paginando."""
        grid_url = f"{self._base_url}/PageStockGrid.aspx"
        await page.goto(grid_url, wait_until="networkidle", timeout=_TIMEOUT_MS)
        await page.fill(_SEL_SEARCH, proveedor)
        await page.keyboard.press("Enter")
        await page.wait_for_load_state("networkidle", timeout=_TIMEOUT_MS)
        await self._delay()

        todos: list[ProductoResumen] = []
        pagina = 1

        while True:
            productos_pagina = await self._extraer_productos_pagina(
                page, proveedor, pagina
            )
            todos.extend(productos_pagina)
            logger.debug(
                f"[Omnimedica] Página {pagina}: {len(productos_pagina)} productos"
            )

            if not await self._ir_a_pagina(page, pagina + 1):
                break
            pagina += 1
            await self._delay()

        return todos

    async def _extraer_productos_pagina(
        self, page: Page, empresa: str, pagina: int
    ) -> list[ProductoResumen]:
        """
        Extrae los productos visibles en la página actual.

        Columnas validadas (9 celdas, índices 0-based):
          [0] vacío  [1] cant_total  [2] disponible  [3] kit
          [4] reservado  [5] codigo  [6] vacío
          [7] empresa  [8] descripcion
        """
        productos = []
        filas = await page.query_selector_all(_SEL_FILAS)

        for idx, fila in enumerate(filas):
            celdas = await fila.query_selector_all("td")
            if len(celdas) < 9:
                continue

            textos = [(await c.inner_text()).strip() for c in celdas]

            codigo = textos[5]
            if not codigo:
                continue

            try:
                productos.append(ProductoResumen(
                    cant_total=int(textos[1]) if textos[1].isdigit() else 0,
                    cant_disponible=int(textos[2]) if textos[2].isdigit() else 0,
                    cant_kit=int(textos[3]) if textos[3].isdigit() else 0,
                    cant_reservado=int(textos[4]) if textos[4].isdigit() else 0,
                    codigo=codigo,
                    empresa=textos[7],
                    descripcion=textos[8],
                    fila_index=idx,
                    pagina=pagina,
                ))
            except (ValueError, IndexError) as exc:
                logger.debug(f"[Omnimedica] Fila ignorada: {exc}")
                continue

        return productos

    async def _ir_a_pagina(self, page: Page, numero: int) -> bool:
        """
        Click en el link de paginación para ir a la página indicada.
        La paginación usa __doPostBack — no hay href real.
        Retorna True si existía el link y navegó, False si no hay más páginas.
        """
        selector = f"a[href*=\"'Page${numero}'\"]"
        link = await page.query_selector(selector)
        if not link:
            return False

        await link.click()
        await page.wait_for_load_state("networkidle", timeout=_TIMEOUT_MS)
        return True

    # ------------------------------------------------------------------
    # Detalle de series por producto
    # ------------------------------------------------------------------

    async def _extraer_series_producto(
        self,
        page: Page,
        producto: ProductoResumen,
        proveedor: str,
    ) -> list[OmnimedicaSerie]:
        """
        Para cada producto:
          1. Reconstruir búsqueda (el filtro se pierde siempre al volver)
          2. Navegar a la página correcta de la grilla
          3. Clickear ImageButton1_N del producto
          4. Parsear el detalle
        """
        # Reconstruir búsqueda y navegar a la página correcta
        grid_url = f"{self._base_url}/PageStockGrid.aspx"
        await page.goto(grid_url, wait_until="networkidle", timeout=_TIMEOUT_MS)
        await page.fill(_SEL_SEARCH, proveedor)
        await page.keyboard.press("Enter")
        await page.wait_for_load_state("networkidle", timeout=_TIMEOUT_MS)
        await self._delay()

        # Paginar hasta llegar a la página del producto
        for p in range(1, producto.pagina):
            await self._ir_a_pagina(page, p + 1)
            await self._delay()

        # Click en el ImageButton de la fila correcta
        btn_id = f"#ContentPlaceHolder1_GridView1_ImageButton1_{producto.fila_index}"
        btn = await page.query_selector(btn_id)

        if not btn:
            logger.warning(
                f"[Omnimedica] ImageButton no encontrado para '{producto.codigo}' "
                f"(fila {producto.fila_index}, pág {producto.pagina})"
            )
            return []

        await btn.click()
        await page.wait_for_load_state("networkidle", timeout=_TIMEOUT_MS)
        await self._delay()

        return await self._parsear_detalle(
            page, producto.codigo, producto.descripcion, producto.empresa
        )

    # ------------------------------------------------------------------
    # Parseo del detalle
    # ------------------------------------------------------------------

    async def _parsear_detalle(
        self,
        page: Page,
        codigo: str,
        descripcion: str,
        empresa: str,
    ) -> list[OmnimedicaSerie]:
        """
        Parsea PageStockGridDetalle.aspx.

        Columnas validadas (9 celdas, índices 0-based):
          [0] vacío  [1] vacío  [2] fecha_ingreso  [3] usuario
          [4] estado  [5] lote  [6] serie
          [7] vencimiento (dd/MM/yyyy)  [8] depósito
        """
        series = []
        filas = await page.query_selector_all(_SEL_FILAS)

        for fila in filas:
            celdas = await fila.query_selector_all("td")
            if len(celdas) < 9:
                continue

            textos = [(await c.inner_text()).strip() for c in celdas]

            estado_raw = textos[4]
            serie_num  = textos[6]
            lote       = textos[5]
            vencimiento = textos[7]
            deposito   = textos[8]

            if not serie_num:
                continue

            kit_match = re.match(r"^KIT\((\d+)\)$", estado_raw, re.IGNORECASE)
            en_transito = bool(kit_match)

            series.append(OmnimedicaSerie(
                codigo=codigo,
                descripcion=descripcion,
                empresa=empresa,
                serie=serie_num,
                lote=lote,
                vencimiento=vencimiento,
                deposito=deposito,
                estado_sistema="kit" if en_transito else "alta",
                en_transito=en_transito,
                kit_numero=kit_match.group(1) if kit_match else None,
            ))

        return series

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _delay(self) -> None:
        await asyncio.sleep(_DELAY_MS / 1000)