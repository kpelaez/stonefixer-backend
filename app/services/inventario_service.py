"""
app/services/inventario_service.py

TEMPORAL (sep-2026): snapshots de stock desde Finnegans guardados en la base
de StoneFixer. Migrar al lakehouse después de la presentación.

Fuente: reporte `resumenStockPorDeposito` (stock a una fecha, valorizado).
Se consulta dos veces (USD y ARS) y se guardan los importes tal cual vienen:
no se convierte moneda en el código.
"""
import logging
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo
from sqlalchemy import delete, func
from sqlmodel import Session, select

from app.config import settings
from app.models.integracion import IntegracionEjecucion
from app.models.inventario import InventarioSnapshot
from app.services.finnegans_client import FinnegansAuthError, FinnegansError, obtener_reporte

logger = logging.getLogger(__name__)

PROCESO = "inventario_snapshot"
_REPORTE = "resumenStockPorDeposito"
_CENTAVOS = Decimal("0.01")
_TZ_AR = ZoneInfo("America/Argentina/Buenos_Aires")


def ayer_argentina() -> date:
    """El día cerrado más reciente según la hora de Argentina (el servidor puede estar en UTC)."""
    return datetime.now(_TZ_AR).date() - timedelta(days=1)

# (deposito_id, deposito, rubro, familia)
Clave = tuple[int, str, str, str]


def _texto(valor: Any) -> str:
    """None y espacios sobrantes -> '' (ver nota del UniqueConstraint en el modelo)."""
    return (valor or "").strip()


def _consultar(fecha: date, moneda: str) -> list[dict[str, Any]]:
    return obtener_reporte(_REPORTE, {
        "fecha": fecha.isoformat(),
        "soloStockNoCero": "true",
        "Empresa": settings.FINNEGANS_EMPRESA,
        "MonedaID": moneda,
    })


def _agrupar(filas: list[dict[str, Any]]) -> dict[Clave, dict[str, Decimal]]:
    grupos: dict[Clave, dict[str, Decimal]] = defaultdict(
        lambda: {"unidades": Decimal(0), "importe": Decimal(0)}
    )
    for f in filas:
        clave = (int(f["DEPOSITOID"]), _texto(f["DEPOSITO"]), _texto(f.get("RUBRO")), _texto(f.get("FAMILIA")))
        grupos[clave]["unidades"] += Decimal(f["CANTIDAD1"] or 0)
        grupos[clave]["importe"] += Decimal(f["IMPORTE"] or 0)
    return grupos


def _tipo_error(exc: Exception) -> str:
    if isinstance(exc, FinnegansAuthError):
        return "credenciales"
    if isinstance(exc, FinnegansError):
        return "finnegans"
    if isinstance(exc, ValueError):
        return "datos"
    return "otro"


def cargar_snapshot(session: Session, fecha: date) -> dict[str, Any]:
    """
    Trae el stock a `fecha` desde Finnegans y lo guarda. Si ya había datos
    para esa fecha, los reemplaza (se puede correr N veces sin duplicar).
    Registra cada ejecución en integracion_ejecucion.
    """
    ejecucion = IntegracionEjecucion(proceso=PROCESO, fecha_datos=fecha, estado="en_curso")
    session.add(ejecucion)
    session.commit()  # se guarda aparte: si el proceso se cuelga, queda el rastro de que arrancó

    try:
        usd = _agrupar(_consultar(fecha, "DOL"))
        ars = _agrupar(_consultar(fecha, "PES"))
        if not usd:
            raise ValueError(f"Finnegans no devolvió stock para {fecha}.")
        if usd.keys() != ars.keys():
            raise ValueError("Las respuestas en USD y ARS no coinciden en depósitos/rubros/familias.")

        # Borrar + insertar + cerrar la ejecución: TODO en una sola transacción.
        session.exec(delete(InventarioSnapshot).where(InventarioSnapshot.fecha == fecha))
        for (deposito_id, deposito, rubro, familia), v in usd.items():
            session.add(InventarioSnapshot(
                fecha=fecha,
                deposito_id=deposito_id,
                deposito=deposito,
                rubro=rubro,
                familia=familia,
                unidades=v["unidades"],
                importe_usd=v["importe"].quantize(_CENTAVOS, rounding=ROUND_HALF_UP),
                importe_ars=ars[(deposito_id, deposito, rubro, familia)]["importe"].quantize(_CENTAVOS, rounding=ROUND_HALF_UP),
            ))
        ejecucion.estado = "ok"
        ejecucion.filas = len(usd)
        ejecucion.finalizado_en = datetime.now(timezone.utc)
        session.add(ejecucion)
        session.commit()

    except Exception as exc:
        session.rollback()  # deshace el borrado: la foto anterior de esa fecha queda intacta
        ejecucion.estado = "error"
        ejecucion.tipo_error = _tipo_error(exc)
        ejecucion.mensaje = str(exc)[:500]
        ejecucion.finalizado_en = datetime.now(timezone.utc)
        session.add(ejecucion)
        session.commit()
        logger.error("Snapshot de inventario %s falló (%s): %s", fecha, ejecucion.tipo_error, exc)
        raise

    return {
        "fecha": fecha,
        "grupos": len(usd),
        "unidades": sum(v["unidades"] for v in usd.values()),
        "importe_usd": sum(v["importe"] for v in usd.values()),
        "importe_ars": sum(v["importe"] for v in ars.values()),
    }

def _totales_por_fecha(session: Session, fechas: list[date]) -> dict[date, dict[str, Decimal]]:
    filas = session.exec(
        select(
            InventarioSnapshot.fecha,
            func.sum(InventarioSnapshot.unidades),
            func.sum(InventarioSnapshot.importe_usd),
            func.sum(InventarioSnapshot.importe_ars),
        )
        .where(InventarioSnapshot.fecha.in_(fechas))
        .group_by(InventarioSnapshot.fecha)
    ).all()
    return {f: {"unidades": u, "importe_usd": usd, "importe_ars": ars} for f, u, usd, ars in filas}


def _variacion(actual: Decimal, anterior: Decimal) -> dict[str, Any]:
    dif = actual - anterior
    return {
        "absoluta": dif,
        # Sin base (cierre en 0) no hay % posible: None, no 0 ni infinito.
        "pct": float((dif / anterior * 100).quantize(_CENTAVOS)) if anterior else None,
    }


def get_resumen(session: Session) -> dict[str, Any] | None:
    """
    Última foto cargada vs. cierre del mes anterior a esa foto.
    Ej.: última foto 23/09 -> se compara contra 31/08.
    """
    fecha_actual = session.exec(select(func.max(InventarioSnapshot.fecha))).one()
    if fecha_actual is None:
        return None

    fecha_cierre = fecha_actual.replace(day=1) - timedelta(days=1)
    totales = _totales_por_fecha(session, [fecha_actual, fecha_cierre])
    actual = totales[fecha_actual]
    cierre = totales.get(fecha_cierre)  # puede no estar cargado todavía

    ultima = session.exec(
        select(IntegracionEjecucion)
        .where(IntegracionEjecucion.proceso == PROCESO)
        .order_by(IntegracionEjecucion.id.desc())
        .limit(1)
    ).first()

    return {
        "fecha": fecha_actual,
        "actual": actual,
        "fecha_cierre_anterior": fecha_cierre,
        "cierre_anterior": cierre,
        "variacion": None if cierre is None else {
            k: _variacion(actual[k], cierre[k]) for k in ("unidades", "importe_usd", "importe_ars")
        },
        "ultima_sincronizacion": None if ultima is None else {
            "estado": ultima.estado,
            "tipo_error": ultima.tipo_error,
            "finalizado_en": ultima.finalizado_en,
        },
    }