# app/services/finnegans_client.py
"""
FinnegansClient — cliente HTTP para la API REST de Finnegans.

Responsabilidad ÚNICA: hablar con los endpoints de Finnegans.
NO maneja autenticación — eso es trabajo de FinnegansCredentialService.

Diseño extensible:
  - Cada endpoint de Finnegans es un método público.
  - Todos comparten la misma sesión httpx y el mismo token.
  - Agregar un endpoint nuevo = agregar un método, nada más.

Endpoints implementados:
  - get_resumen_stock_por_deposito() → resumenStockPorDeposito por depósito/empresa

Depósitos configurados (extensible vía lista):
  - "GENERAL"       → Omnimedica Central
  - "DISTRIBUCION"  → Depósito Distribución

Nota sobre el formato de la API:
  - Los números vienen como float nativo (ej: 16.0), NO como string formateado.
  - PARTIDA_VTO con valor '01-01-1900' es la fecha nula de Finnegans → None.
  - ESTADOPARTIDA puede venir como None si el producto no tiene partida.

Uso:
    token = await FinnegansCredentialService.get_valid_token(db)
    async with FinnegansClient(token) as client:
        stock = await client.get_stock_empresa_todos_depositos(empresa="OMNI34")
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constantes de configuración
# ------------------------------------------------------------------

_BASE_URL = "https://api.finneg.com/api"
_SEMAPHORE_LIMIT = 5
_TIMEOUT_SECONDS = 45.0
_MONEDA_DEFAULT = "ARS"
_FECHA_STOCK = "getCurrentDate"

# Fecha nula de Finnegans — se trata como "sin vencimiento"
_FECHA_NULA_FINNEGANS = "01-01-1900"

# Depósitos a consultar — agregar aquí para escalar sin tocar código
DEPOSITOS_INVENTARIO: list[str] = [
    "GENERAL",       # Omnimedica Central
    "DISTRIBUCION",  # Depósito Distribución
]


# ------------------------------------------------------------------
# Data classes de respuesta
# ------------------------------------------------------------------

@dataclass
class StockItem:
    """
    Un ítem del reporte resumenStockPorDeposito.
    Refleja los campos reales devueltos por Finnegans (validados con test).
    """
    # Identificación
    producto_id: int
    producto_codigo: str
    producto_nombre: str
    deposito_id: int
    deposito: str

    # Cantidades (vienen como float desde Finnegans)
    stock_disponible: Decimal
    stock_reservado: Decimal
    cantidad: Decimal
    punto_reposicion: Decimal
    cantidad_a_reponer: Decimal

    # Partida / vencimiento
    partida: Optional[str]
    partida_vto: Optional[date]      # None si Finnegans devuelve "01-01-1900"
    estado_partida: Optional[str]

    # Clasificación
    marca: Optional[str]
    familia: Optional[str]
    subfamilia: Optional[str]
    rubro: Optional[str]
    concepto_producto: Optional[str]

    # Financiero
    precio_unitario: Optional[Decimal]
    importe: Optional[Decimal]
    moneda: Optional[str]
    cotizacion: Optional[Decimal]

    # Extra
    activo: bool = True
    unidad: Optional[str] = None

    @property
    def stock_neto(self) -> Decimal:
        """Stock disponible menos reservado."""
        return self.stock_disponible - self.stock_reservado

    @property
    def necesita_reposicion(self) -> bool:
        """True si el stock disponible está por debajo del punto de reposición."""
        return (
            self.punto_reposicion > Decimal("0")
            and self.stock_disponible < self.punto_reposicion
        )


# ------------------------------------------------------------------
# Cliente principal
# ------------------------------------------------------------------

class FinnegansClient:
    """
    Cliente HTTP para Finnegans.

    Siempre usar como context manager:
        async with FinnegansClient(token) as client:
            ...
    """

    def __init__(self, access_token: str) -> None:
        self._token = access_token
        self._semaphore = asyncio.Semaphore(_SEMAPHORE_LIMIT)
        self._http: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "FinnegansClient":
        self._http = httpx.AsyncClient(
            base_url=_BASE_URL,
            timeout=httpx.Timeout(_TIMEOUT_SECONDS),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._http:
            await self._http.aclose()

    # ------------------------------------------------------------------
    # Endpoint: resumenStockPorDeposito
    # ------------------------------------------------------------------

    async def get_resumen_stock_por_deposito(
        self,
        empresa: str,
        deposito: Optional[str] = None,
        producto: Optional[str] = None,
        solo_stock_no_cero: bool = True,
        fecha: str = _FECHA_STOCK,
        moneda: str = _MONEDA_DEFAULT,
    ) -> list[StockItem]:
        """
        Consulta el reporte resumenStockPorDeposito de Finnegans.

        Args:
            empresa:           Código de empresa (ej: "OMNI34")
            deposito:          Código de depósito (ej: "GENERAL"). None = todos.
            producto:          Código de producto para filtrar. None = todos.
            solo_stock_no_cero: Filtrar productos sin stock.
            fecha:             Fecha hasta (yyyy-MM-dd o constante relativa).
            moneda:            Código de moneda (requerido por Finnegans).

        Returns:
            Lista de StockItem parseados.
        """
        async with self._semaphore:
            params: dict = {
                "ACCESS_TOKEN": self._token,
                "PARAMWEBREPORT_Empresa": empresa,
                "PARAMWEBREPORT_MonedaID": moneda,
                "PARAMWEBREPORT_fecha": fecha,
                "PARAMWEBREPORT_soloStockNoCero": str(solo_stock_no_cero).lower(),
                "PARAMWEBREPORT_soloStockDebajoPtoReposicion": "false",
                "PARAMWEBREPORT_tipoStock": "0",
                "PARAMWEBREPORT_TipoPrecio": "0",
                "PARAMWEBREPORT_AgruparPor": "1",
                "PARAMWEBREPORT_soloDepositos": "0",
            }

            if deposito:
                params["PARAMWEBREPORT_deposito"] = deposito
            if producto:
                params["PARAMWEBREPORT_producto"] = producto

            try:
                response = await self._http.get(
                    "/reports/resumenStockPorDeposito",
                    params=params,
                )
                response.raise_for_status()
                raw_data = response.json()

                items = self._parsear_stock_items(raw_data, deposito or "TODOS")
                logger.info(
                    f"[Finnegans] resumenStockPorDeposito → empresa={empresa} "
                    f"deposito={deposito or 'todos'} → {len(items)} items"
                )
                return items

            except httpx.HTTPStatusError as exc:
                logger.error(
                    f"[Finnegans] HTTP {exc.response.status_code} en "
                    f"resumenStockPorDeposito: {exc.response.text[:300]}"
                )
                return []
            except httpx.RequestError as exc:
                logger.error(f"[Finnegans] Error de conexión: {exc}")
                return []

    async def get_stock_empresa_todos_depositos(
        self,
        empresa: str,
        depositos: list[str] = DEPOSITOS_INVENTARIO,
        moneda: str = _MONEDA_DEFAULT,
    ) -> dict[str, list[StockItem]]:
        """
        Consulta todos los depósitos configurados en paralelo.

        Returns:
            Dict {codigo_deposito: [StockItem, ...]}

        Ejemplo:
            {
                "GENERAL": [StockItem(...), ...],
                "DISTRIBUCION": [StockItem(...), ...]
            }
        """
        tasks = [
            self.get_resumen_stock_por_deposito(
                empresa=empresa,
                deposito=dep,
                moneda=moneda,
            )
            for dep in depositos
        ]

        resultados = await asyncio.gather(*tasks, return_exceptions=False)

        mapping = dict(zip(depositos, resultados))

        total = sum(len(v) for v in mapping.values())
        logger.info(
            f"[Finnegans] Consulta multi-depósito completada: "
            f"{total} items en {len(depositos)} depósitos"
        )
        return mapping

    def get_stock_por_codigo(
        self,
        items: list[StockItem],
        producto_codigo: str,
    ) -> Decimal:
        """
        Helper: suma el stock disponible de un código en todos los items.
        Útil para comparar contra Omnimedica después del scraping.
        """
        total = Decimal("0")
        for item in items:
            if item.producto_codigo == producto_codigo:
                total += item.stock_disponible
        return total

    # ------------------------------------------------------------------
    # Parsing interno
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Parsing interno
    # ------------------------------------------------------------------

    @staticmethod
    def _parsear_float(valor) -> Decimal:
        """
        Convierte el valor numérico de Finnegans a Decimal.
        La API devuelve floats nativos (ej: 16.0), no strings formateados.
        Maneja None y valores vacíos.
        """
        if valor is None or valor == "":
            return Decimal("0")
        try:
            return Decimal(str(valor))
        except Exception:
            logger.warning(f"[Finnegans] No se pudo parsear número: {valor!r}")
            return Decimal("0")

    @staticmethod
    def _parsear_fecha_vto(valor: Optional[str]) -> Optional[date]:
        """
        Parsea la fecha de vencimiento de Finnegans.
        '01-01-1900' es la fecha nula → retorna None.
        Formato esperado: 'dd-MM-yyyy'
        """
        if not valor or valor.strip() == _FECHA_NULA_FINNEGANS:
            return None
        try:
            from datetime import datetime
            return datetime.strptime(valor.strip(), "%d-%m-%Y").date()
        except ValueError:
            logger.debug(f"[Finnegans] Fecha de vencimiento no parseable: '{valor}'")
            return None

    @staticmethod
    def _parsear_stock_items(
        raw_data: list | dict,
        deposito_hint: str,
    ) -> list[StockItem]:
        """
        Parsea la respuesta de Finnegans a lista de StockItem.
        La API puede devolver una lista o un dict (un solo item).
        Campos validados contra respuesta real del test del 2026-06-08.
        """
        if isinstance(raw_data, dict):
            raw_data = [raw_data]

        if not isinstance(raw_data, list):
            logger.warning(
                f"[Finnegans] Formato de respuesta inesperado: {type(raw_data)}"
            )
            return []

        p = FinnegansClient._parsear_float
        items = []

        for row in raw_data:
            try:
                items.append(
                    StockItem(
                        # Identificación
                        producto_id=int(row.get("PRODUCTOID") or 0),
                        producto_codigo=str(row.get("PRODUCTOCODIGO") or "").strip(),
                        producto_nombre=str(row.get("PRODUCTO") or "").strip(),
                        deposito_id=int(row.get("DEPOSITOID") or 0),
                        deposito=str(row.get("DEPOSITO") or deposito_hint).strip(),

                        # Cantidades
                        stock_disponible=p(row.get("STOCKDISPONIBLE")),
                        stock_reservado=p(row.get("STOCKRESERVADO")),
                        cantidad=p(row.get("CANTIDAD1")),
                        punto_reposicion=p(row.get("PUNTOREPOSICION")),
                        cantidad_a_reponer=p(row.get("CANTIDADSTOCKAREPONER")),

                        # Partida / vencimiento
                        partida=row.get("PARTIDA") or None,
                        partida_vto=FinnegansClient._parsear_fecha_vto(
                            row.get("PARTIDA_VTO")
                        ),
                        estado_partida=row.get("ESTADOPARTIDA"),

                        # Clasificación
                        marca=row.get("MARCA"),
                        familia=row.get("FAMILIA"),
                        subfamilia=row.get("SUBFAMILIA"),
                        rubro=row.get("RUBRO"),
                        concepto_producto=row.get("CONCEPTOPRODUCTO"),

                        # Financiero
                        precio_unitario=p(row.get("PRECIOUNIDADSTOCK1")),
                        importe=p(row.get("IMPORTE")),
                        moneda=row.get("MONEDA"),
                        cotizacion=p(row.get("COTIZACION")),

                        # Extra
                        activo=bool(row.get("ACTIVO", True)),
                        unidad=row.get("UNIDAD1"),
                    )
                )
            except Exception as exc:
                logger.warning(
                    f"[Finnegans] Error parseando fila "
                    f"(codigo={row.get('PRODUCTOCODIGO')}): {exc}"
                )
                continue

        return items