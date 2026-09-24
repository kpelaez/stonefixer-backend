"""
app/api/routes/contribucion_marginal_routes.py

Expone los KPIs agregados de Contribución Marginal (fuente: lakehouse,
prod.cont_marg_gen) para el Panel Ejecutivo y el dashboard de CM.

Permisos: admin/manager (misma convención que /dashboards en el frontend).
No expone paciente/médico/institución — eso queda para el detalle por OT,
en otra ruta con su propio control de acceso.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
import logging

from app.api.deps import require_manager
from app.models.user import User
from app.db.lakehouse_database import get_lakehouse_db
from app.services.contribucion_marginal_service import (
    get_kpis_periodo,
    get_kpis_por_mes,
    get_registros as get_registros_svc,
    get_ranking_clientes as get_ranking_clientes_svc,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/kpis")
def get_contribucion_marginal_kpis(
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_lakehouse_db),
):
    """
    Totales de Contribución Marginal del período (o rango de fechas).

    Query params opcionales:
      - fecha_desde: 'YYYY-MM-DD'
      - fecha_hasta: 'YYYY-MM-DD'
    """
    try:
        return get_kpis_periodo(db, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    except Exception as e:
        logger.error(f"Error obteniendo KPIs de Contribución Marginal: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al consultar el lakehouse. Intentá de nuevo en unos minutos.",
        )


@router.get("/registros")
def get_registros(
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    cliente: str | None = None,
    search: str | None = None,
    order_by: str = "fecha_factura",
    order_dir: str = "desc",
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_lakehouse_db),
):
    """Listado fila por fila para la tabla de OTs del dashboard de CM."""
    try:
        return get_registros_svc(
            db, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
            cliente=cliente, search=search, order_by=order_by, order_dir=order_dir,
            limit=limit, offset=offset,
        )
    except Exception as e:
        logger.error(f"Error obteniendo registros de Contribución Marginal: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al consultar el lakehouse. Intentá de nuevo en unos minutos.",
        )


@router.get("/ranking-clientes")
def get_ranking_clientes(
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    limit: int = 20,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_lakehouse_db),
):
    """Top clientes por contribución marginal, para el gráfico de ranking."""
    try:
        return get_ranking_clientes_svc(db, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, limit=limit)
    except Exception as e:
        logger.error(f"Error obteniendo ranking de clientes: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al consultar el lakehouse. Intentá de nuevo en unos minutos.",
        )
@router.get("/kpis/por-mes")
def get_contribucion_marginal_kpis_por_mes(
    meses: int = 12,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_lakehouse_db),
):
    """Breakdown mes a mes (últimos N meses), para gráficos de tendencia."""
    try:
        return get_kpis_por_mes(db, meses=meses)
    except Exception as e:
        logger.error(f"Error obteniendo KPIs mensuales de Contribución Marginal: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al consultar el lakehouse. Intentá de nuevo en unos minutos.",
        )