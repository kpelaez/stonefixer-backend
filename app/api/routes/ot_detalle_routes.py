"""
app/api/routes/ot_detalle_routes.py

Expone el detalle completo de una OT para el OTDetalleModal. Trae
paciente/médico/institución (PII) — mismo control de acceso que el
resto del módulo de Contribución Marginal.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
import logging

from app.api.deps import require_manager
from app.models.user import User
from app.db.lakehouse_database import get_lakehouse_db
from app.services.ot_detalle_service import get_ot_detalle_completo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{cont_marg_gen_id}")
def get_ot_detalle(
    cont_marg_gen_id: int,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_lakehouse_db),
):
    try:
        detalle = get_ot_detalle_completo(db, cont_marg_gen_id)
    except Exception as e:
        logger.error(f"Error obteniendo detalle de OT {cont_marg_gen_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error al consultar el lakehouse. Intentá de nuevo en unos minutos.",
        )

    if detalle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el registro {cont_marg_gen_id} en Contribución Marginal.",
        )

    return detalle