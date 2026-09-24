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
from datetime import date
from decimal import Decimal
from typing import Optional, Any
from sqlmodel import Session
from sqlalchemy import text


class PeriodoInvalido(ValueError):
    """El rango pedido no se puede resolver con las filas de la vista gold."""


def periodo_desde_fechas(fecha_desde: Optional[str], fecha_hasta: Optional[str]) -> Optional[date]:
    """
    El frontend manda primer y último día del mes. La vista gold solo tiene
    filas MES y TOTAL, así que traducimos:
      - sin fechas               -> None (fila TOTAL)
      - fechas del mismo mes     -> primer día del mes (fila MES)
      - fechas de meses distintos -> PeriodoInvalido
    """
    if not fecha_desde and not fecha_hasta:
        return None

    try:
        desde = date.fromisoformat(fecha_desde) if fecha_desde else None
        hasta = date.fromisoformat(fecha_hasta) if fecha_hasta else None
    except ValueError as exc:
        raise PeriodoInvalido("Formato de fecha inválido, se espera YYYY-MM-DD.") from exc

    ref = desde or hasta
    otra = hasta or desde
    if (ref.year, ref.month) != (otra.year, otra.month):
        raise PeriodoInvalido("Solo se puede consultar un mes completo o el total.")

    return ref.replace(day=1)


_GOLD_COLUMNS = """
    periodo,
    venta_bruta,
    costos_ppp,
    gastos_logisticos,
    gastos_comerciales,
    contribucion_marginal,
    porcentaje_costos,
    porcentaje_gastos_logisticos,
    porcentaje_gastos_comerciales,
    porcentaje_margen,
    ultima_actualizacion,
    gastos_comerciales_asignados,
    gastos_comerciales_sin_asignar,
    porcentaje_gastos_comerciales_asignados,
    porcentaje_gastos_comerciales_sin_asignar,
    gastos_comerciales_vendedor,
    gastos_comerciales_tecnico,
    porcentaje_gastos_comerciales_vendedor,
    porcentaje_gastos_comerciales_tecnico
"""


def _gold_a_respuesta(row: Any) -> dict:
    """
    Traduce la fila de la Gold al JSON del endpoint. Las primeras claves
    mantienen los nombres que YA usa el frontend, para poder desplegar el
    backend antes que el frontend sin romper la pantalla.
    """
    return {
        "venta_bruta": row.venta_bruta,
        "costos": row.costos_ppp,
        "gastos_logisticos": row.gastos_logisticos,
        "margen": row.contribucion_marginal,
        "pct_costos": row.porcentaje_costos,
        "pct_gastos": row.porcentaje_gastos_logisticos,
        "pct_margen": row.porcentaje_margen,
        "ultima_actualizacion": row.ultima_actualizacion,
        # Nuevos: gasto comercial
        "gastos_comerciales": row.gastos_comerciales,
        "pct_gastos_comerciales": row.porcentaje_gastos_comerciales,
        "gastos_comerciales_asignados": row.gastos_comerciales_asignados,
        "gastos_comerciales_sin_asignar": row.gastos_comerciales_sin_asignar,
        "pct_gc_asignados": row.porcentaje_gastos_comerciales_asignados,      # sobre el total
        "pct_gc_sin_asignar": row.porcentaje_gastos_comerciales_sin_asignar,  # sobre el total
        "gastos_comerciales_vendedor": row.gastos_comerciales_vendedor,
        "gastos_comerciales_tecnico": row.gastos_comerciales_tecnico,
        "pct_gc_vendedor": row.porcentaje_gastos_comerciales_vendedor,        # sobre lo asignado
        "pct_gc_tecnico": row.porcentaje_gastos_comerciales_tecnico,          # sobre lo asignado
    }


def get_kpis_periodo(
    session: Session,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
) -> Optional[dict]:
    """Fila TOTAL o MES de prod.gold_cm_kpis_periodo. None si el mes no existe."""
    periodo = periodo_desde_fechas(fecha_desde, fecha_hasta)

    if periodo is None:
        query = f"SELECT {_GOLD_COLUMNS} FROM prod.gold_cm_kpis_periodo WHERE tipo_periodo = 'TOTAL'"
        params = {}
    else:
        query = f"""
            SELECT {_GOLD_COLUMNS} FROM prod.gold_cm_kpis_periodo
            WHERE tipo_periodo = 'MES' AND periodo = :periodo
        """
        params = {"periodo": periodo}

    row = session.exec(text(query), params=params).first()
    return _gold_a_respuesta(row) if row is not None else None


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
    """Últimos N meses de la Gold (filas MES), más reciente primero."""
    query = f"""
        SELECT {_GOLD_COLUMNS} FROM prod.gold_cm_kpis_periodo
        WHERE tipo_periodo = 'MES'
        ORDER BY periodo DESC
        LIMIT :meses
    """
    rows = session.exec(text(query), params={"meses": meses}).all()
    return [{"mes_anio": r.periodo.strftime("%Y-%m"), **_gold_a_respuesta(r)} for r in rows]