#!/usr/bin/env python
# scripts/diagnostics/test_omnimedica.py
"""
Script de prueba AISLADO para validar el scraper de Omnimedica.

Selectores validados contra HTML real (2026-06-08):
  - Usuario:  input[name="Login1$UserName"]
  - Password: input[name="Login1$Password"]
  - Submit:   input[name="Login1$LoginButton"]
  - Buscador: input[name="ctl00$ContentPlaceHolder1$TextBox_Search"]
  - Filas:    tr.grid_row, tr.grid_alt_row
  - Detalle:  #ContentPlaceHolder1_GridView1_ImageButton1_N

Flujo:
  redir.omnimedica.com.ar → CONTINUAR MANUALMENTE → login (IP real) → stock grid
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
_base = Path(__file__).resolve().parent.parent.parent
load_dotenv(_base / ".env.development")

import os
OMNI_USER      = os.getenv("OMNI_USER", "")
OMNI_PASSWORD  = os.getenv("OMNI_PASSWORD", "")
PROVEEDOR_TEST = "ARGENTINA MEDICAL PRODUCTS SRL"

_REDIR_URL  = "http://redir.omnimedica.com.ar"
_SEL_SEARCH = 'input[name="ctl00$ContentPlaceHolder1$TextBox_Search"]'
_SEL_FILAS  = "tr.grid_row, tr.grid_alt_row"
_TIMEOUT_MS = 30_000
_DELAY_S    = 2.0


async def main():
    print("=" * 55)
    print("  Test scraper Omnimedica — StoneFixer")
    print("=" * 55)

    if not OMNI_USER or not OMNI_PASSWORD:
        print("❌ OMNI_USER o OMNI_PASSWORD no están en .env.development")
        sys.exit(1)

    print(f"Usuario: {OMNI_USER}")

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(ignore_https_errors=True)
        page    = await context.new_page()

        # ── PASO 1: Redir → servidor activo ───────────────────────────
        print(f"\n━━━ PASO 1: Redir → servidor activo ━━━")
        await page.goto(_REDIR_URL, wait_until="domcontentloaded", timeout=_TIMEOUT_MS)
        await asyncio.sleep(_DELAY_S)

        btn_continuar = await page.query_selector("text=CONTINUAR MANUALMENTE")
        if btn_continuar:
            print("✅ Haciendo click en 'CONTINUAR MANUALMENTE'")
            await btn_continuar.click()
            await page.wait_for_load_state("networkidle", timeout=_TIMEOUT_MS)
            await asyncio.sleep(_DELAY_S)
        else:
            print("⚠️  Botón no encontrado — esperando redirección automática")
            await asyncio.sleep(5)

        from urllib.parse import urlparse
        base_url = f"{urlparse(page.url).scheme}://{urlparse(page.url).netloc}"
        print(f"Servidor activo: {base_url}")

        # ── PASO 2: Login con selectores validados ─────────────────────
        print(f"\n━━━ PASO 2: Login ━━━")
        print(f"URL: {page.url}")

        # Selectores exactos del HTML real
        await page.fill('input[name="Login1$UserName"]', OMNI_USER)
        await page.fill('input[name="Login1$Password"]', OMNI_PASSWORD)
        await page.click('input[name="Login1$LoginButton"]')
        await page.wait_for_load_state("networkidle", timeout=_TIMEOUT_MS)
        await asyncio.sleep(_DELAY_S)

        post_login_url = page.url
        print(f"Post-login URL: {post_login_url}")

        # Verificar si el login fue exitoso
        # Si sigue en la misma página con el form de login → falló
        login_form = await page.query_selector('input[name="Login1$LoginButton"]')
        if login_form:
            print("❌ Login fallido — el formulario sigue visible")
            print("   Verificar OMNI_USER y OMNI_PASSWORD en .env.development")
            # Mostrar si hay mensaje de error en la página
            error_msg = await page.query_selector(".failureNotification, span[id*='Failure']")
            if error_msg:
                msg = await error_msg.inner_text()
                print(f"   Mensaje de error: {msg!r}")
            await asyncio.sleep(10)
            await browser.close()
            sys.exit(1)

        print("✅ Login exitoso")

        # Recalcular base_url por si cambió
        base_url = f"{urlparse(page.url).scheme}://{urlparse(page.url).netloc}"

        # ── PASO 3: PageStockGrid ──────────────────────────────────────
        print(f"\n━━━ PASO 3: PageStockGrid.aspx ━━━")
        grid_url = f"{base_url}/PageStockGrid.aspx"
        print(f"Navegando a: {grid_url}")
        await page.goto(grid_url, wait_until="networkidle", timeout=_TIMEOUT_MS)
        await asyncio.sleep(_DELAY_S)
        print(f"URL actual: {page.url}")

        if "Error" in page.url or "error" in page.url:
            print("❌ Redirigió a página de error — sesión no válida")
            await asyncio.sleep(10)
            await browser.close()
            sys.exit(1)

        # Buscar el input de búsqueda
        search = await page.query_selector(_SEL_SEARCH)
        if not search:
            print(f"❌ Buscador no encontrado: {_SEL_SEARCH}")
            print("   Inputs disponibles:")
            for inp in await page.query_selector_all("input"):
                n = await inp.get_attribute("name") or ""
                t = await inp.get_attribute("type") or ""
                print(f"     type={t!r} name={n!r}")
            await asyncio.sleep(15)
            await browser.close()
            sys.exit(1)

        print(f"✅ Buscador encontrado")

        # ── PASO 4: Buscar proveedor ───────────────────────────────────
        print(f"\n━━━ PASO 4: Buscar '{PROVEEDOR_TEST}' ━━━")
        await search.fill(PROVEEDOR_TEST)
        await page.keyboard.press("Enter")
        await page.wait_for_load_state("networkidle", timeout=_TIMEOUT_MS)
        await asyncio.sleep(_DELAY_S)

        filas = await page.query_selector_all(_SEL_FILAS)
        print(f"✅ {len(filas)} filas en primera página")

        if not filas:
            print("❌ Sin resultados — verificar nombre del proveedor")
            await asyncio.sleep(10)
            await browser.close()
            sys.exit(1)

        # Mostrar columnas de la primera fila
        primera  = filas[0]
        celdas   = await primera.query_selector_all("td")
        textos   = [(await c.inner_text()).strip() for c in celdas]
        print(f"\nColumnas primera fila ({len(textos)} celdas):")
        for i, t in enumerate(textos):
            print(f"  [{i}] {t!r}")

        # Paginación
        links = await page.query_selector_all("a[href*='Page$']")
        print(f"\nLinks de paginación: {len(links)}")
        for lnk in links[:5]:
            txt = (await lnk.inner_text()).strip()
            print(f"  {txt!r}")

        # ── PASO 5: Detalle del primer producto ────────────────────────
        print(f"\n━━━ PASO 5: Detalle primer producto (ImageButton1_0) ━━━")
        btn = await page.query_selector(
            "#ContentPlaceHolder1_GridView1_ImageButton1_0"
        )
        if not btn:
            print("❌ ImageButton1_0 no encontrado")
            print("   Todos los image buttons disponibles:")
            btns = await page.query_selector_all("input[type='image']")
            for b in btns[:5]:
                bid   = await b.get_attribute("id")   or ""
                bname = await b.get_attribute("name") or ""
                print(f"     id={bid!r} name={bname!r}")
            await asyncio.sleep(15)
            await browser.close()
            sys.exit(1)

        print("Click en ImageButton1_0...")
        await btn.click()
        await page.wait_for_load_state("networkidle", timeout=_TIMEOUT_MS)
        await asyncio.sleep(_DELAY_S)
        print(f"URL detalle: {page.url}")

        # Extraer filas del detalle
        filas_det = await page.query_selector_all(_SEL_FILAS)
        print(f"Filas en detalle: {len(filas_det)}")

        if filas_det:
            print("\nPrimeras 3 filas del detalle:")
            for fila in filas_det[:3]:
                celdas = await fila.query_selector_all("td")
                textos = [(await c.inner_text()).strip() for c in celdas]
                print(f"  ({len(textos)} celdas) {textos}")

        print("\n" + "=" * 55)
        print("  ✅ Test completado exitosamente")
        print("=" * 55)
        await asyncio.sleep(5)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())