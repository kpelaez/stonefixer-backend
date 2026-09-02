"""
KPIs y periodos del Panel Ejecutivo.

La fuente unica de esta pantalla es la vista de solo lectura
``prod.kpi_panel_ejecutivo``. Las sumas y los porcentajes ya vienen
resueltos por PostgreSQL; este servicio solo selecciona la fila anual o
mensual solicitada y expone los periodos disponibles.

Se conserva el nombre historico del modulo para no duplicar servicios ni
romper sus imports actuales. Si el equipo decide renombrarlo a
``panel_ejecutivo_service.py``, conviene hacerlo como un refactor separado.
"""
from typing import Optional

from sqlalchemy import text
from sqlmodel import Session


_KPI_COLUMNS = """
    tipo_periodo,
    periodo,
    periodo_nombre,
    anio_mes_orden,
    facturado,
    cobrado,
    contribucion_marginal,
    giro_negocio_pct,
    venta_bruta_cm,
    contribucion_marginal_pct,
    anio,
    mes
"""


def get_facturado_cobrado_periodo(
    session: Session,
    anio: Optional[int] = None,
    mes: Optional[int] = None,
) -> Optional[dict]:
    """Devuelve la fila anual o mensual solicitada para el Panel Ejecutivo.

    Si ``anio`` no se informa, utiliza el ultimo anio disponible. ``mes`` es
    opcional: sin mes se consulta el acumulado ``ANIO``; con mes se consulta
    la fila ``MES`` correspondiente.

    No calcula importes ni porcentajes. Si el periodo no existe, devuelve
    ``None`` para que la ruta responda 404.
    """
    if anio is None:
        anio_row = session.exec(
            text(
                "SELECT MAX(anio) AS anio_predeterminado "
                "FROM prod.kpi_panel_ejecutivo"
            )
        ).first()
        anio = anio_row.anio_predeterminado if anio_row is not None else None

    if anio is None:
        return None

    if mes is None:
        query = f"""
            SELECT {_KPI_COLUMNS}
            FROM prod.kpi_panel_ejecutivo
            WHERE tipo_periodo = 'ANIO'
              AND anio = :anio
              AND mes IS NULL
        """
        params = {"anio": anio}
    else:
        query = f"""
            SELECT {_KPI_COLUMNS}
            FROM prod.kpi_panel_ejecutivo
            WHERE tipo_periodo = 'MES'
              AND anio = :anio
              AND mes = :mes
        """
        params = {"anio": anio, "mes": mes}

    row = session.exec(text(query), params=params).first()
    return dict(row._mapping) if row is not None else None


def get_facturado_cobrado_por_mes(session: Session) -> dict:
    """Devuelve anios y meses existentes para construir filtros dinamicos."""
    anio_row = session.exec(
        text(
            "SELECT MAX(anio) AS anio_predeterminado "
            "FROM prod.kpi_panel_ejecutivo"
        )
    ).first()
    anio_predeterminado = (
        anio_row.anio_predeterminado if anio_row is not None else None
    )

    anio_rows = session.exec(
        text(
            """
            SELECT DISTINCT anio
            FROM prod.kpi_panel_ejecutivo
            WHERE anio IS NOT NULL
            ORDER BY anio DESC
            """
        )
    ).all()

    periodo_rows = session.exec(
        text(
            """
            SELECT
                periodo,
                periodo_nombre,
                anio_mes_orden,
                anio,
                mes
            FROM prod.kpi_panel_ejecutivo
            WHERE tipo_periodo = 'MES'
              AND anio IS NOT NULL
              AND mes IS NOT NULL
            ORDER BY anio_mes_orden DESC
            """
        )
    ).all()

    return {
        "anio_predeterminado": anio_predeterminado,
        "anios": [row.anio for row in anio_rows],
        "periodos": [dict(row._mapping) for row in periodo_rows],
    }
