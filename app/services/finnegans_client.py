"""
app/services/finnegans_client.py

Cliente mínimo de la API de Finnegans (ERP).

SEGURIDAD — leer antes de tocar:
Finnegans recibe client_secret y ACCESS_TOKEN como query params, así que la
URL completa ES un secreto. Por eso:
  - httpx loguea cada URL en nivel INFO: se sube su logger a WARNING.
  - Los mensajes de error nunca incluyen la URL.
  - Se usa `raise ... from None` para que el traceback no arrastre la
    excepción original de httpx, que sí incluye la URL.
"""
import json
import logging
from decimal import Decimal
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

_TIMEOUT = httpx.Timeout(connect=10.0, read=90.0, write=10.0, pool=10.0)


class FinnegansError(RuntimeError):
    """Error al consultar Finnegans. El mensaje nunca incluye URL ni credenciales."""

class FinnegansAuthError(FinnegansError):
    """Finnegans rechazó client_id/secret. Requiere acción humana: regenerar las keys del usuario de API."""


def _get(client: httpx.Client, path: str, params: dict[str, str], que: str, error_http: type[FinnegansError] = FinnegansError) -> httpx.Response:
    try:
        resp = client.get(f"{settings.FINNEGANS_BASE_URL}{path}", params=params)
    except httpx.TimeoutException:
        raise FinnegansError(f"Timeout consultando {que} en Finnegans.") from None
    except httpx.HTTPError as exc:
        raise FinnegansError(f"Error de red consultando {que}: {type(exc).__name__}.") from None
    if resp.status_code != 200:
        raise error_http(f"Finnegans respondió HTTP {resp.status_code} al consultar {que}.")
    return resp


def _obtener_token(client: httpx.Client) -> str:
    if not settings.FINNEGANS_CLIENT_ID or not settings.FINNEGANS_CLIENT_SECRET:
        raise FinnegansError("Faltan FINNEGANS_CLIENT_ID / FINNEGANS_CLIENT_SECRET en el entorno.")
    resp = _get(
        client,
        "/oauth/token",
        {
            "grant_type": "client_credentials",
            "client_id": settings.FINNEGANS_CLIENT_ID,
            "client_secret": settings.FINNEGANS_CLIENT_SECRET,
        },
        "el token",
        error_http=FinnegansAuthError,
    )
    token = resp.text.strip().strip('"')  # Finnegans devuelve el token como texto plano
    if not token:
        raise FinnegansError("Finnegans devolvió un token vacío.")
    return token


def obtener_reporte(codigo: str, parametros: dict[str, str]) -> list[dict[str, Any]]:
    """
    Ejecuta un reporte de Finnegans. `parametros` va sin el prefijo:
    {"fecha": "2026-09-22"} se envía como PARAMWEBREPORT_fecha=2026-09-22.
    Los números se parsean como Decimal, nunca float.
    """
    params = {f"PARAMWEBREPORT_{k}": v for k, v in parametros.items()}
    with httpx.Client(timeout=_TIMEOUT) as client:
        token = _obtener_token(client)
        resp = _get(client, f"/reports/{codigo}", {"ACCESS_TOKEN": token, **params}, f"el reporte {codigo}")
    return json.loads(resp.text, parse_float=Decimal)