"""
app/services/ot_detalle_service.py

Sirve el OTDetalleModal completo: dado un id de cont_marg_gen, resuelve
sus tres transacciones relacionadas (OT, factura, consumo) y arma:
  - Datos operativos (paciente/médico/institución) — desde ot_cabecera,
    NO desde cont_marg_gen (ver nota en app/models/ot.py sobre por qué).
  - "Producto(s) Vendido(s)" — desde comprobante_venta_detalle.
  - "Desglose de Productos Consumidos" — desde consumo_detalle (ya existía).

Cualquiera de las tres relaciones puede faltar (transaccion_id_* es
nullable en cont_marg_gen) — el service devuelve esas secciones vacías
en vez de fallar, igual que hace hoy el modal con Excel cuando falta
alguna hoja.
"""
from decimal import Decimal
from typing import Optional
from sqlmodel import Session, select

from app.models.contribucion_marginal import ContribucionMarginal
from app.models.consumo import CabeceraConsumo, ConsumoDetalle
from app.models.comprobante_venta import ComprobanteVentaCabecera, ComprobanteVentaDetalle
from app.models.ot import OtCabecera, OtDetalle


def _get_consumo(session: Session, transaccion_id_consumo: Optional[int]) -> Optional[dict]:
    if transaccion_id_consumo is None:
        return None

    cabecera = session.exec(
        select(CabeceraConsumo).where(
            CabeceraConsumo.transaccion_id_consumo == transaccion_id_consumo
        )
    ).first()
    if cabecera is None:
        return None

    detalle_rows = session.exec(
        select(ConsumoDetalle)
        .where(ConsumoDetalle.transaccion_id_consumo == transaccion_id_consumo)
        .order_by(ConsumoDetalle.importe.desc())
    ).all()
    total_importe = sum((row.importe for row in detalle_rows), Decimal(0))

    return {
        "nro_remito": cabecera.nro_remito,
        "importe_total": cabecera.importe_total,
        "productos": [
            {
                "producto": row.producto,
                "precio": row.precio,
                "cantidad": row.cantidad,
                "unidad": row.unidad,
                "importe": row.importe,
                "pct_participacion": float(row.importe / total_importe * 100) if total_importe else 0.0,
            }
            for row in detalle_rows
        ],
    }


def _get_productos_vendidos(
    session: Session,
    transaccion_id_factura: Optional[int],
    transaccion_id_ot: Optional[int],
) -> Optional[dict]:
    """
    ⚠️ Heurística — confirmar con Martín cuando se pueda.

    Una factura puede agrupar productos de VARIAS OTs distintas en el
    mismo comprobante. Traer comprobante_venta_detalle filtrando solo
    por transaccion_id_factura devuelve TODOS esos productos, no solo
    los de esta OT — de ahí que apareciera un ítem "de otra operación"
    en el modal.

    Fix: usar ot_detalle.codigo_producto (que sí está scopeado
    correctamente a transaccion_id_ot) como filtro sobre los productos
    de la factura. Si la OT no tiene filas en ot_detalle (o no se pasó
    transaccion_id_ot), se hace fallback al comportamiento anterior sin
    filtrar — mejor mostrar de más que ocultar de más en ese caso raro.
    """
    if transaccion_id_factura is None:
        return None

    cabecera = session.exec(
        select(ComprobanteVentaCabecera).where(
            ComprobanteVentaCabecera.transaccion_id == transaccion_id_factura
        )
    ).first()
    if cabecera is None:
        return None

    detalle_rows = session.exec(
        select(ComprobanteVentaDetalle).where(
            ComprobanteVentaDetalle.transaccion_id == transaccion_id_factura
        )
    ).all()

    if transaccion_id_ot is not None:
        codigos_ot = {
            c for c in session.exec(
                select(OtDetalle.codigo_producto).where(OtDetalle.transaccion_id == transaccion_id_ot)
            ).all()
            if c is not None
        }
        if codigos_ot:
            detalle_rows = [r for r in detalle_rows if r.codigo_producto in codigos_ot]

    return {
        "comprobante": cabecera.comprobante,
        "cliente": cabecera.cliente,
        "total": cabecera.total,
        "productos": [
            {
                "producto": row.producto,
                "cantidad": row.cantidad,
                "unidad_venta": row.unidad_venta,
                "precio": row.precio,
                "importe": row.importe,
                "familia": row.familia,
                "subfamilia": row.subfamilia,
            }
            for row in detalle_rows
        ],
    }


def _get_info_operativa(session: Session, transaccion_id_ot: Optional[int], cm: ContribucionMarginal) -> dict:
    """
    Paciente/médico/institución: preferir ot_cabecera (fuente futura),
    con fallback a las columnas de cont_marg_gen mientras conviven ambas.
    """
    ot_cab = None
    if transaccion_id_ot is not None:
        ot_cab = session.exec(
            select(OtCabecera).where(OtCabecera.transaccion_id == transaccion_id_ot)
        ).first()

    return {
        "paciente": (ot_cab.paciente if ot_cab else None) or cm.paciente,
        "medico": (ot_cab.medico if ot_cab else None) or cm.medico,
        "medico_proctor": (ot_cab.medico_proctor if ot_cab else None) or cm.medico_proctor,
        "institucion": (ot_cab.institucion if ot_cab else None) or cm.institucion,
        "tecnico": (ot_cab.tecnico_1 if ot_cab else None) or cm.tecnico,
        "fuente": "ot_cabecera" if ot_cab else "cont_marg_gen (legacy, ot_cabecera no encontrada)",
    }


def get_ot_detalle_completo(session: Session, cont_marg_gen_id: int) -> Optional[dict]:
    """Punto de entrada único del OTDetalleModal — arma las 3 secciones."""
    cm = session.get(ContribucionMarginal, cont_marg_gen_id)
    if cm is None:
        return None

    return {
        "resumen_financiero": {
            "venta_bruta": cm.total_bruto_factura,
            "costo": cm.precio,
            "gastos_logisticos": cm.gastos_logisticos,
            "contribucion_marginal": cm.contribucion_marginal,
            "pct_margen": cm.porcentaje_margen,
        },
        "info_operativa": _get_info_operativa(session, cm.transaccion_id_ot, cm),
        "producto_vendido": _get_productos_vendidos(session, cm.transaccion_id_factura, cm.transaccion_id_ot),
        "consumo": _get_consumo(session, cm.transaccion_id_consumo),
    }