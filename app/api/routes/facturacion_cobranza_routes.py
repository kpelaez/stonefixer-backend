"""
app/api/routes/facturacion_cobranza_routes.py
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
import logging

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
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_lakehouse_db),
):
    try:
        return get_facturado_cobrado_periodo(db, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    except Exception as e:
        logger.error(f"Error obteniendo KPIs de facturación/cobranza: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al consultar el lakehouse. Intentá de nuevo en unos minutos.",
        )


@router.get("/kpis/por-mes")
def get_kpis_por_mes(
    meses: int = 12,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_lakehouse_db),
):
    try:
        return get_facturado_cobrado_por_mes(db, meses=meses)
    except Exception as e:
        logger.error(f"Error obteniendo KPIs mensuales de facturación/cobranza: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al consultar el lakehouse. Intentá de nuevo en unos minutos.",
        )