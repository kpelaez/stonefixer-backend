"""
app/services/contribucion_marginal_service.py

Replica la lógica de KPIs que hoy calcula ContribucionMarginalDashboard.tsx
client-side desde el Excel. Devuelve SOLO agregados — no expone paciente/
médico/institución acá (eso queda para el detalle por OT, en otro service).

Regla de negocio:
  - Se agrupa por mes/año de fecha_factura. [CONFIRMADO con Kevin, 14/07]

  - Notas de crédito (nro_nc): [CONFIRMADO con datos reales, 14/07]
    Las filas con nro_nc SE INCLUYEN en el cálculo (no se excluyen).
    venta_bruta, costos y gastos_logisticos toman el valor original de
    la factura (actividad operativa real, aunque después se haya
    acreditado). El neteo del impacto de la NC sobre la rentabilidad
    ya viene reflejado en la propia columna contribucion_marginal por
    fila — confirmado con muestra real que NO siempre da 0: cuando
    hay gastos_logisticos ya incurridos sobre una factura con NC total,
    contribucion_marginal queda NEGATIVO (pérdida real), reflejando
    venta_neta(post-NC) - costos - gastos correctamente por fila.
    Por eso alcanza con sumar contribucion_marginal tal cual, sin
    resta manual de total_bruto_nc — la columna ya viene bien calculada
    desde el lakehouse.
"""
from decimal import Decimal
from typing import Optional
from sqlmodel import Session
from sqlalchemy import text


def _calc_kpis(venta_bruta: Decimal, costos: Decimal, gastos_log: Decimal, margen: Decimal) -> dict:
    """Calcula los porcentajes derivados, igual que el useMemo del frontend."""
    venta_bruta = venta_bruta or Decimal(0)
    costos = costos or Decimal(0)
    gastos_log = gastos_log or Decimal(0)
    margen = margen or Decimal(0)

    return {
        "venta_bruta": venta_bruta,
        "costos": costos,
        "gastos_logisticos": gastos_log,
        "margen": margen,
        "pct_margen": float(margen / venta_bruta * 100) if venta_bruta else 0.0,
        "pct_gastos": float(gastos_log / venta_bruta * 100) if venta_bruta else 0.0,
        "pct_costos": float(costos / venta_bruta * 100) if venta_bruta else 0.0,
    }


def get_kpis_periodo(
    session: Session,
    fecha_desde: Optional[str] = None,  # 'YYYY-MM-DD'
    fecha_hasta: Optional[str] = None,
) -> dict:
    """
    Totales del período completo (o filtrado por rango de fechas si se pasa).
    Equivalente a 'kpis' cuando selectedMes === 'todos' en el frontend actual.
    """
    query = f"""
        SELECT
            COALESCE(SUM(total_bruto_factura), 0) AS venta_bruta,
            COALESCE(SUM(precio), 0) AS costos,
            COALESCE(SUM(gastos_logisticos), 0) AS gastos_logisticos,
            COALESCE(SUM(contribucion_marginal), 0) AS margen,
            MAX(fecha_carga) AS ultima_actualizacion
        FROM prod.cont_marg_gen
        WHERE 1=1
        {"AND fecha_factura >= :fecha_desde" if fecha_desde else ""}
        {"AND fecha_factura <= :fecha_hasta" if fecha_hasta else ""}
    """
    params = {}
    if fecha_desde:
        params["fecha_desde"] = fecha_desde
    if fecha_hasta:
        params["fecha_hasta"] = fecha_hasta

    row = session.exec(text(query), params=params).first()

    kpis = _calc_kpis(row.venta_bruta, row.costos, row.gastos_logisticos, row.margen)
    kpis["ultima_actualizacion"] = row.ultima_actualizacion
    return kpis


_ORDENABLES = {
    "fecha_factura", "contribucion_marginal", "porcentaje_margen",
    "total_bruto_factura", "precio", "gastos_logisticos", "cliente", "nro_ot",
}


def get_registros(
    session: Session,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    cliente: Optional[str] = None,
    search: Optional[str] = None,
    order_by: str = "fecha_factura",
    order_dir: str = "desc",
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """
    Listado fila por fila para la tabla de OTs del dashboard.
    NO incluye paciente/médico/institución (eso es solo para el modal
    de detalle, con su propio control de acceso) — acá va lo mínimo
    para armar la tabla y disparar el click hacia el modal.

    `search` busca simultáneamente en cliente, nro_ot y nro_factura
    (para la búsqueda libre del frontend). `cliente` es un filtro exacto
    aparte (usado cuando se hace click en una barra del gráfico) — ambos
    se pueden combinar (se aplican con AND).

    order_by whitelisteado contra _ORDENABLES (nunca interpolar el
    parámetro crudo del usuario en el ORDER BY sin esto).
    """
    if order_by not in _ORDENABLES:
        order_by = "fecha_factura"
    order_dir = "ASC" if order_dir.lower() == "asc" else "DESC"

    query = f"""
        SELECT
            id, fecha_factura, nro_factura, cliente, nro_ot, nro_remito,
            total_bruto_factura, precio, gastos_logisticos,
            contribucion_marginal, porcentaje_margen,
            sucursal, estado_valorizacion, descripcion_ppp
        FROM prod.cont_marg_gen
        WHERE 1=1
        {"AND fecha_factura >= :fecha_desde" if fecha_desde else ""}
        {"AND fecha_factura <= :fecha_hasta" if fecha_hasta else ""}
        {"AND cliente ILIKE :cliente" if cliente else ""}
        {"AND (cliente ILIKE :search OR nro_ot ILIKE :search OR nro_factura ILIKE :search)" if search else ""}
        {"AND nro_ot IS NOT NULL AND total_bruto_factura > 0 AND porcentaje_margen < 99.9" if order_by == "porcentaje_margen" else ""}
        ORDER BY {order_by} {order_dir} NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    params = {"limit": limit, "offset": offset}
    if fecha_desde:
        params["fecha_desde"] = fecha_desde
    if fecha_hasta:
        params["fecha_hasta"] = fecha_hasta
    if cliente:
        params["cliente"] = f"%{cliente}%"
    if search:
        params["search"] = f"%{search}%"

    rows = session.exec(text(query), params=params).all()
    return [dict(row._mapping) for row in rows]


def get_ranking_clientes(
    session: Session,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Top clientes por contribución marginal, para el gráfico de ranking."""
    query = f"""
        SELECT
            cliente,
            COALESCE(SUM(total_bruto_factura), 0) AS venta_bruta,
            COALESCE(SUM(contribucion_marginal), 0) AS margen,
            COUNT(*) AS cantidad_ots
        FROM prod.cont_marg_gen
        WHERE cliente IS NOT NULL
        {"AND fecha_factura >= :fecha_desde" if fecha_desde else ""}
        {"AND fecha_factura <= :fecha_hasta" if fecha_hasta else ""}
        GROUP BY cliente
        ORDER BY margen DESC
        LIMIT :limit
    """
    params = {"limit": limit}
    if fecha_desde:
        params["fecha_desde"] = fecha_desde
    if fecha_hasta:
        params["fecha_hasta"] = fecha_hasta

    rows = session.exec(text(query), params=params).all()
    return [
        {
            "cliente": row.cliente,
            "venta_bruta": row.venta_bruta,
            "margen": row.margen,
            "pct_margen": float(row.margen / row.venta_bruta * 100) if row.venta_bruta else 0.0,
            "cantidad_ots": row.cantidad_ots,
        }
        for row in rows
    ]


def get_kpis_por_mes(session: Session, meses: int = 12) -> list[dict]:
    """
    Breakdown mes a mes (últimos N meses), agrupado por fecha_factura.
    Equivalente a lo que arma mesesDisponibles + filtro por selectedMes
    en el frontend actual, pero resuelto en una sola query en vez de
    filtrar en el cliente.
    """
    query = f"""
        SELECT
            TO_CHAR(fecha_factura, 'YYYY-MM') AS mes_anio,
            COALESCE(SUM(total_bruto_factura), 0) AS venta_bruta,
            COALESCE(SUM(precio), 0) AS costos,
            COALESCE(SUM(gastos_logisticos), 0) AS gastos_logisticos,
            COALESCE(SUM(contribucion_marginal), 0) AS margen
        FROM prod.cont_marg_gen
        WHERE fecha_factura IS NOT NULL
        GROUP BY TO_CHAR(fecha_factura, 'YYYY-MM')
        ORDER BY mes_anio DESC
        LIMIT :meses
    """
    rows = session.exec(text(query), params={"meses": meses}).all()

    return [
        {
            "mes_anio": row.mes_anio,
            **_calc_kpis(row.venta_bruta, row.costos, row.gastos_logisticos, row.margen),
        }
        for row in rows
    ]