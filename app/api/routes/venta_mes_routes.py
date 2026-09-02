from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session
from typing import Optional

from app.db.lakehouse_database import get_lakehouse_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.venta_mes import VentaMesKpis
from app.services.venta_mes_service import get_venta_mes_kpis

router = APIRouter()

@router.get("/kpis", response_model=VentaMesKpis)
async def get_venta_mes_kpis_endpoint(
    fecha_desde: Optional[str] = Query(None, description="YYYY-MM-DD"),
    fecha_hasta: Optional[str] = Query(None, description="YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    lakehouse_db: Session = Depends(get_lakehouse_db),
):
    try:
        return get_venta_mes_kpis(lakehouse_db, fecha_desde, fecha_hasta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo venta del mes: {str(e)}")