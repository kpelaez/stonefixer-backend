"""
app/api/routes/facturacion_cobranza_routes.py
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.deps import require_manager
from app.models.user import User
from app.db.lakehouse_database import get_lakehouse_db
from app.services.facturacion_cobranza_service import (
    get_facturado_cobrado_periodo,
    get_facturado_cobrado_por_mes,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/kpis")
def get_kpis(
    anio: int | None = Query(default=None, ge=2026),
    mes: int | None = Query(default=None, ge=1, le=12),
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_lakehouse_db),
):
    try:
        kpis = get_facturado_cobrado_periodo(db, anio=anio, mes=mes)
    except Exception as e:
        logger.error(f"Error obteniendo KPIs del Panel Ejecutivo: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al consultar el lakehouse. Intentá de nuevo en unos minutos.",
        )

    if kpis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existen datos para el período solicitado.",
        )

    return kpis


@router.get("/kpis/por-mes")
def get_kpis_por_mes(
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_lakehouse_db),
):
    try:
        return get_facturado_cobrado_por_mes(db)
    except Exception as e:
        logger.error(f"Error obteniendo períodos del Panel Ejecutivo: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al consultar el lakehouse. Intentá de nuevo en unos minutos.",
        )
