#!/usr/bin/env python
# scripts/test_finnegans.py
"""
Script de prueba AISLADO para validar la integración con Finnegans.

Corre sin FastAPI, sin BD, sin ninguna dependencia del proyecto.
Usá esto para validar las credenciales y ver la estructura real
de la respuesta antes de conectar todo al service.

Uso:
    cd backend
    python scripts/test_finnegans.py

Requiere en el entorno (o en .env.development):
    FINNEGANS_CLIENT_ID=...
    FINNEGANS_CLIENT_SECRET=...
"""

import asyncio
import os
import sys
from pathlib import Path

# Cargar .env antes de cualquier import del proyecto
from dotenv import load_dotenv
_base = Path(__file__).resolve().parent.parent.parent
load_dotenv(_base / ".env.development")

import httpx

# ------------------------------------------------------------------
# Credenciales desde .env (no hardcodear nunca)
# ------------------------------------------------------------------
CLIENT_ID = os.getenv("FINNEGANS_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("FINNEGANS_CLIENT_SECRET", "")
AUTH_URL = "https://api.finneg.com/api/oauth/token"
REPORTS_URL = "https://api.finneg.com/api/reports"

EMPRESA = "OMNI34"
DEPOSITOS = ["GENERAL", "DISTRIBUCION"]
MONEDA = "PES"


async def obtener_token() -> dict:
    """Paso 1: obtener token OAuth2."""
    print("\n━━━ PASO 1: Obtener token OAuth2 ━━━")
    async with httpx.AsyncClient(timeout=30.0) as http:
        response = await http.get(
            AUTH_URL,
            params={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "detailed": "1",
            },
        )

    print(f"Status: {response.status_code}")
    data = response.json()

    # Mostrar sin exponer el token completo
    print(f"User:      {data.get('User')}")
    print(f"Domain:    {data.get('Domain')}")
    print(f"CreatedAt: {data.get('CreatedAt')}")
    print(f"ExpiresAt: {data.get('ExpiresAt')}")
    print(f"Token:     {data.get('Token', '')[:8]}...{data.get('Token', '')[-4:]}")

    if not data.get("Token"):
        print("❌ No se obtuvo token. Verificar credenciales.")
        sys.exit(1)

    print("✅ Token obtenido OK")
    return data


async def consultar_deposito(token: str, deposito: str) -> list:
    """Paso 2: consultar stock de un depósito."""
    print(f"\n━━━ PASO 2: Consultar depósito '{deposito}' ━━━")
    async with httpx.AsyncClient(timeout=45.0) as http:
        response = await http.get(
            f"{REPORTS_URL}/resumenStockPorDeposito",
            params={
                "ACCESS_TOKEN": token,
                "PARAMWEBREPORT_Empresa": EMPRESA,
                "PARAMWEBREPORT_deposito": deposito,
                "PARAMWEBREPORT_MonedaID": MONEDA,
                "PARAMWEBREPORT_fecha": "getCurrentDate",
                "PARAMWEBREPORT_soloStockNoCero": "true",
                "PARAMWEBREPORT_soloStockDebajoPtoReposicion": "false",
                "PARAMWEBREPORT_tipoStock": "0",
                "PARAMWEBREPORT_TipoPrecio": "0",
                "PARAMWEBREPORT_AgruparPor": "1",
                "PARAMWEBREPORT_soloDepositos": "0",
            },
        )

    print(f"Status: {response.status_code}")

    if response.status_code != 200:
        print(f"❌ Error: {response.text[:300]}")
        return []

    data = response.json()

    # Puede ser lista o dict
    if isinstance(data, dict):
        data = [data]

    print(f"✅ {len(data)} items recibidos")

    # Mostrar primeros 3 para validar estructura
    print("\nEjemplo de estructura (primeros 3 items):")
    for item in data[:3]:
        print(f"  PRODUCTOCODIGO: {item.get('PRODUCTOCODIGO')}")
        print(f"  PRODUCTO:       {item.get('PRODUCTO')}")
        print(f"  DEPOSITO:       {item.get('DEPOSITO')}")
        print(f"  STOCKDISPONIBLE:{item.get('STOCKDISPONIBLE')}")
        print(f"  CANTIDAD1:      {item.get('CANTIDAD1')}")
        print(f"  STOCKRESERVADO: {item.get('STOCKRESERVADO')}")
        print(f"  ESTADOPARTIDA:  {item.get('ESTADOPARTIDA')}")
        print("  ---")

    # Mostrar todos los campos del primer item para detectar campos nuevos
    if data:
        print(f"\nTodos los campos del primer item:")
        for k, v in data[0].items():
            print(f"  {k}: {v!r}")

    return data


async def main():
    print("=" * 50)
    print("  Test integración Finnegans — StoneFixer")
    print("=" * 50)

    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ FINNEGANS_CLIENT_ID o FINNEGANS_CLIENT_SECRET no están en .env")
        print("   Agregalos al archivo .env.development:")
        print("   FINNEGANS_CLIENT_ID=tu_client_id")
        print("   FINNEGANS_CLIENT_SECRET=tu_client_secret")
        sys.exit(1)

    # Paso 1: token
    token_data = await obtener_token()
    token = token_data["Token"]

    # Paso 2: consultar cada depósito
    for deposito in DEPOSITOS:
        await consultar_deposito(token, deposito)

    print("\n" + "=" * 50)
    print("  Test completado")
    print("=" * 50)
    print("\n✅ Si ves items arriba, la integración está lista.")
    print("   Copiá los nombres exactos de los campos y")
    print("   verificá que PRODUCTOCODIGO coincida con los")
    print("   códigos que trae Omnimedica.")


if __name__ == "__main__":
    asyncio.run(main())