"""
app/services/facturacion_cobranza_service.py

KPIs de Facturado / Cobrado / Giro de Negocio para el Panel Ejecutivo.

Filtros confirmados con datos reales (14/08, Kevin):

FACTURADO — comprobante_venta_cabecera.transaccion_subtipo_id:
  Facturas reales (suman positivo):
    266 = Factura de Venta Electrónica Iva Incluido
    267 = Factura de Venta Omnimedica Iva Incluido
    190 = Factura de Venta Electrónica
    281 = Factura de Crédito Electrónica FCE (factura MiPyme, cuenta como venta)
  Notas de crédito (RESTAN — netean el facturado, no se excluyen):
    282, 269, 145, 191 = Nota de Crédito (FCE / Electrónica / Ventas)
  PENDIENTE de decidir con negocio: 192 = Nota de Débito de Venta
  Electrónica — hoy queda EXCLUIDA (postura conservadora, no infla el
  número), pero si una Nota de Débito debería sumar al facturado
  (aumenta lo que el cliente debe), avisame y la agrego a la lista de
  incluidos.

COBRADO — cabecera_cobranzas.tipo_movimiento:
  COBRANZA = cobro real (positivo)
  DEVCOB   = devolución de cobranza (se resta, neteando el cobro real)
  Ambos con estado='Activa' — no hay otros estados en la muestra, pero
  si aparece algo distinto de 'Activa' en el futuro, revisar si debe
  excluirse (ej. un estado 'Anulada').
"""
from decimal import Decimal
from typing import Optional
from sqlmodel import Session
from sqlalchemy import text

_SUBTIPOS_FACTURA = (266, 267, 190, 281, 192)
_SUBTIPOS_NC = (282, 269, 145, 191)
_SUBTIPOS_FACTURA_SQL = ", ".join(str(s) for s in _SUBTIPOS_FACTURA)
_SUBTIPOS_NC_SQL = ", ".join(str(s) for s in _SUBTIPOS_NC)


def get_facturado_cobrado_periodo(
    session: Session,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
) -> dict:
    facturado_query = f"""
        SELECT COALESCE(SUM(
            CASE
                WHEN transaccion_subtipo_id IN ({_SUBTIPOS_FACTURA_SQL}) THEN total
                WHEN transaccion_subtipo_id IN ({_SUBTIPOS_NC_SQL}) THEN total
                ELSE 0
            END
        ), 0) AS facturado
        FROM prod.comprobante_venta_cabecera
        WHERE transaccion_subtipo_id IN ({_SUBTIPOS_FACTURA_SQL}, {_SUBTIPOS_NC_SQL})
        {"AND fecha_comprobante >= :fecha_desde" if fecha_desde else ""}
        {"AND fecha_comprobante <= :fecha_hasta" if fecha_hasta else ""}
    """
    cobrado_query = f"""
        SELECT COALESCE(SUM(
            CASE WHEN tipo_movimiento = 'DEVCOB' THEN importe_total ELSE importe_total END
        ), 0) AS cobrado
        FROM prod.cabecera_cobranzas
        WHERE tipo_movimiento IN ('COBRANZA', 'DEVCOB')
          AND estado = 'Activa'
        {"AND fecha_cobranza >= :fecha_desde" if fecha_desde else ""}
        {"AND fecha_cobranza <= :fecha_hasta" if fecha_hasta else ""}
    """
    params = {}
    if fecha_desde:
        params["fecha_desde"] = fecha_desde
    if fecha_hasta:
        params["fecha_hasta"] = fecha_hasta

    facturado = session.exec(text(facturado_query), params=params).first().facturado
    cobrado = session.exec(text(cobrado_query), params=params).first().cobrado

    giro_negocio = float(cobrado / facturado * 100) if facturado else 0.0

    return {
        "facturado": facturado,
        "cobrado": cobrado,
        "giro_negocio_pct": giro_negocio,
    }


def get_facturado_cobrado_por_mes(session: Session, meses: int = 12) -> list[dict]:
    query = f"""
        WITH fact AS (
            SELECT TO_CHAR(fecha_comprobante, 'YYYY-MM') AS mes_anio,
                   COALESCE(SUM(
                       CASE
                           WHEN transaccion_subtipo_id IN ({_SUBTIPOS_FACTURA_SQL}) THEN total
                           WHEN transaccion_subtipo_id IN ({_SUBTIPOS_NC_SQL}) THEN total
                           ELSE 0
                       END
                   ), 0) AS facturado
            FROM prod.comprobante_venta_cabecera
            WHERE transaccion_subtipo_id IN ({_SUBTIPOS_FACTURA_SQL}, {_SUBTIPOS_NC_SQL})
            GROUP BY TO_CHAR(fecha_comprobante, 'YYYY-MM')
        ),
        cob AS (
            SELECT TO_CHAR(fecha_cobranza, 'YYYY-MM') AS mes_anio,
                   COALESCE(SUM(
                       CASE WHEN tipo_movimiento = 'DEVCOB' THEN importe_total ELSE importe_total END
                   ), 0) AS cobrado
            FROM prod.cabecera_cobranzas
            WHERE tipo_movimiento IN ('COBRANZA', 'DEVCOB') AND estado = 'Activa'
            GROUP BY TO_CHAR(fecha_cobranza, 'YYYY-MM')
        )
        SELECT
            COALESCE(fact.mes_anio, cob.mes_anio) AS mes_anio,
            COALESCE(fact.facturado, 0) AS facturado,
            COALESCE(cob.cobrado, 0) AS cobrado
        FROM fact
        FULL OUTER JOIN cob ON fact.mes_anio = cob.mes_anio
        ORDER BY mes_anio DESC
        LIMIT :meses
    """
    rows = session.exec(text(query), params={"meses": meses}).all()
    return [
        {
            "mes_anio": row.mes_anio,
            "facturado": row.facturado,
            "cobrado": row.cobrado,
            "giro_negocio_pct": float(row.cobrado / row.facturado * 100) if row.facturado else 0.0,
        }
        for row in rows
    ]