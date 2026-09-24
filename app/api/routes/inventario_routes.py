"""
app/api/routes/inventario_routes.py

TEMPORAL (sep-2026): inventario desde snapshots guardados en la base de StoneFixer.
"""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.deps import PermissionChecker, require_admin
from app.db.database import get_db
from app.models.user import User
from app.services.finnegans_client import FinnegansAuthError, FinnegansError
from app.services.inventario_service import ayer_argentina, cargar_snapshot, get_resumen

router = APIRouter()
logger = logging.getLogger(__name__)

_TZ_AR = ZoneInfo("America/Argentina/Buenos_Aires")


@router.get("/resumen")
def get_inventario_resumen(
    current_user: User = Depends(PermissionChecker(module_code="dashboards", action="view")),
    db: Session = Depends(get_db),
):
    """Última foto de stock vs. cierre del mes anterior. Lee solo de la base, nunca del ERP."""
    resumen = get_resumen(db)
    if resumen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todavía no hay fotos de inventario cargadas.")
    return resumen


@router.post("/snapshots")
def post_inventario_snapshot(
    fecha: date | None = Query(default=None, description="YYYY-MM-DD. Por defecto: ayer (hora Argentina)."),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Carga (o recarga) la foto de stock de una fecha desde Finnegans. Solo admin."""
    hoy = datetime.now(_TZ_AR).date()
    fecha = fecha or ayer_argentina()
    if fecha >= hoy:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Solo se pueden cargar días cerrados (anteriores a hoy).",
        )

    try:
        return cargar_snapshot(db, fecha)
    except FinnegansAuthError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Finnegans rechazó las credenciales. Revisar las keys del usuario de API.",
        )
    except FinnegansError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))