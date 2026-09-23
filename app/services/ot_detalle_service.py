"""
app/services/ot_detalle_service.py

Sirve el OTDetalleModal completo: dado un id de cont_marg_gen, resuelve
sus tres transacciones relacionadas (OT, factura, consumo) y arma:
  - Datos operativos (paciente/médico/institución) — desde ot_cabecera,
    NO desde cont_marg_gen (ver nota en app/models/ot.py sobre por qué).
  - Tarjetas y composicion - desde prod.gold_cm_modal_kpis (nivel OT)
  - "Producto(s) Vendido(s)" - desde prod.gold_cm_modal_productos_vendidos.
  - "Desglose de Productos Consumidos" — desde consumo_detalle (ya existía).

Cualquiera de las tres relaciones puede faltar (transaccion_id_* es
nullable en cont_marg_gen) — el service devuelve esas secciones vacías
en vez de fallar, igual que hace hoy el modal con Excel cuando falta
alguna hoja.
"""
from decimal import Decimal
from typing import Optional
from sqlalchemy import text
from sqlmodel import Session, select

from app.models.contribucion_marginal import ContribucionMarginal
from app.models.consumo import CabeceraConsumo, ConsumoDetalle
from app.models.ot import OtCabecera


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


_MODAL_KPI_COLUMNS = """
    nro_ot,
    venta_bruta,
    costos_ppp,
    gastos_logisticos,
    gastos_comerciales,
    gastos_comerciales_vendedor,
    gastos_comerciales_tecnico,
    contribucion_marginal,
    porcentaje_costos,
    porcentaje_gastos_logisticos,
    porcentaje_gastos_comerciales,
    porcentaje_margen,
    cantidad_personas_asignadas,
    ultima_actualizacion
"""


def _get_resumen_financiero(session: Session, transaccion_id_ot: Optional[int]) -> Optional[dict]:
    """
    Tarjetas y composición del modal, a nivel OT, desde prod.gold_cm_modal_kpis.
    La Gold ya resuelve CM = venta - PPP - logísticos - comerciales y todos
    los %: acá solo se lee, no se calcula nada.
    """
    if transaccion_id_ot is None:
        return None

    row = session.exec(
        text(f"SELECT {_MODAL_KPI_COLUMNS} FROM prod.gold_cm_modal_kpis WHERE transaccion_id_ot = :ot"),
        params={"ot": transaccion_id_ot},
    ).first()
    if row is None:
        return None

    return {
        "nro_ot": row.nro_ot,
        "venta_bruta": row.venta_bruta,
        "costo": row.costos_ppp,                  # se mantiene el nombre que ya usa el frontend
        "gastos_logisticos": row.gastos_logisticos,
        "gastos_comerciales": row.gastos_comerciales,
        "gastos_comerciales_vendedor": row.gastos_comerciales_vendedor,
        "gastos_comerciales_tecnico": row.gastos_comerciales_tecnico,
        "contribucion_marginal": row.contribucion_marginal,
        "pct_costos": row.porcentaje_costos,
        "pct_gastos_logisticos": row.porcentaje_gastos_logisticos,
        "pct_gastos_comerciales": row.porcentaje_gastos_comerciales,
        "pct_margen": row.porcentaje_margen,
        "cantidad_personas_asignadas": row.cantidad_personas_asignadas,
        "ultima_actualizacion": row.ultima_actualizacion,
    }


def _get_productos_vendidos(session: Session, transaccion_id_ot: Optional[int]) -> Optional[dict]:
    """
    Productos vendidos de la OT desde prod.gold_cm_modal_productos_vendidos.
    La vista vincula cada ítem del remito con su línea de factura, así que
    reemplaza la heurística anterior por codigo_producto.
    """
    if transaccion_id_ot is None:
        return None

    rows = session.exec(
        text("""
            SELECT nro_factura, producto, producto_remito,
                   cantidad_facturada, cantidad_remitida, unidad_venta,
                   precio_unitario_bruto, importe_bruto_item,
                   moneda, familia, subfamilia, estado_vinculacion
            FROM prod.gold_cm_modal_productos_vendidos
            WHERE transaccion_id_ot = :ot
            ORDER BY importe_bruto_item DESC NULLS LAST
        """),
        params={"ot": transaccion_id_ot},
    ).all()
    if not rows:
        return None

    # Una OT puede tener más de una factura
    facturas = sorted({r.nro_factura for r in rows if r.nro_factura})

    return {
        "comprobante": ", ".join(facturas),
        "productos": [
            {
                "nro_factura": r.nro_factura,
                # Si el ítem remitido no tiene factura vinculada, se muestra lo remitido
                "producto": r.producto or r.producto_remito,
                "cantidad": r.cantidad_facturada if r.cantidad_facturada is not None else r.cantidad_remitida,
                "unidad_venta": r.unidad_venta,
                "precio": r.precio_unitario_bruto,
                "importe": r.importe_bruto_item,
                "moneda": r.moneda,
                "familia": r.familia,
                "subfamilia": r.subfamilia,
                "estado_vinculacion": r.estado_vinculacion,
            }
            for r in rows
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
    """
    Punto de entrada del OTDetalleModal. Recibe el id de una fila de
    cont_marg_gen, resuelve su OT y arma las secciones.
    Las tarjetas y los productos son de la OT COMPLETA (vistas gold), no
    de la fila puntual.
    """
    cm = session.get(ContribucionMarginal, cont_marg_gen_id)
    if cm is None:
        return None

    return {
        "resumen_financiero": _get_resumen_financiero(session, cm.transaccion_id_ot),
        "info_operativa": _get_info_operativa(session, cm.transaccion_id_ot, cm),
        "producto_vendido": _get_productos_vendidos(session, cm.transaccion_id_ot),
        "consumo": _get_consumo(session, cm.transaccion_id_consumo),
    }