from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from datetime import datetime

from app.db.database import get_db
from app.models.user import User
from app.api.deps import get_current_user, require_roles

# Modelos de Mantenimiento
from app.models.asset_maintenance import (
    AssetMaintenanceCreate,
    AssetMaintenanceRead,
    AssetMaintenanceUpdate,
    AssetMaintenanceWithDetails,
    StartMaintenance,
    CompleteMaintenance,
    MaintenanceType,
    MaintenanceStatus,
    MaintenanceMetrics,
    MaintenancePriority,
    MaintenanceSchedule
)

from app.services.asset_maintenance_service import (
    create_maintenance,
    get_maintenance,
    get_maintenances,
    update_maintenance,
    delete_maintenance,
    start_maintenance,
    complete_maintenance,
    cancel_maintenance,
    get_asset_maintenance_history,
    get_upcoming_maintenances,
    get_overdue_maintenances,
    get_maintenance_metrics,
    schedule_preventive_maintenance
)

router = APIRouter()

@router.post("/", response_model=AssetMaintenanceRead, status_code=status.HTTP_201_CREATED)
@require_roles(["admin", "inventory_manager"])
async def create_maintenance_endpoint(maintenance: AssetMaintenanceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Crear un nuevo registro de mantenimiento"""
    try: 
        # Si no se especifica quien lo solicitó, usar el usuario actual
        if not maintenance.requested_by_user_id:
            maintenance.requested_by_user_id = current_user.id

        return create_maintenance(db, maintenance)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    

@router.get("/", response_model=List[AssetMaintenanceWithDetails])
async def get_maintenances_endpoint(status: MaintenanceStatus, maintenance_type: MaintenanceType, priority: Optional[MaintenancePriority] = None, asset_id: Optional[int] = None, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None, db: Session = Depends(get_db)):
    """Obtener lista de mantenimientos con filtros"""
    return get_maintenances(db, status, maintenance_type, priority, asset_id,date_from, date_to)

@router.get("/{maintenance_id}", response_model=AssetMaintenanceWithDetails)
async def get_maintenance_endpoint(maintenance_id: int, db: Session = Depends(get_db)):
    """Obtener un mantenimiento especifico"""
    maintenance = get_maintenance(db, maintenance_id)
    if not maintenance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mantenimiento no encontrado")
    
    return maintenance

@router.patch("/{maintenance_id}", response_model=AssetMaintenanceRead)
@require_roles(["admin", "inventory_manager"])
async def update_maintenance_endpoint(maintenance_id: int, maintenance_update: AssetMaintenanceUpdate, db: Session = Depends(get_db)):
    """Actualizar un mantenimiento"""
    try: 
        maintenance = update_maintenance(db, maintenance_id, maintenance_update)
        if not maintenance:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mantenimiento no encontrado")
        return maintenance
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{maintenance_id}/start", response_model= AssetMaintenanceRead)
@require_roles(["admin", "inventory_manager"])
async def start_maintenance_endpoint(maintenance_id: int, start_data: StartMaintenance ,db: Session = Depends(get_db)):
    """Iniciar un mantenimiento"""
    try:
        maintenance = start_maintenance(db,maintenance_id, start_data)
        if not maintenance:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mantenimiento no encontrado")
        return maintenance
    except ValueError as e: 
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    

@router.post("/{maintenance_id}/complete", response_model=AssetMaintenanceRead)
@require_roles(["admin", "inventory_manager"])
async def complete_maintenance_endpoint(maintenance_id: int,complete_data: CompleteMaintenance, db: Session = Depends(get_db)):
    """Completar un mantenimiento"""
    try: 
        maintenance = complete_maintenance(db, maintenance_id, complete_data)
        if not maintenance:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mantenimiento no encontrado")
        return maintenance
    except ValueError as e: 
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{maintenance_id}/cancel", response_model=AssetMaintenanceRead)
@require_roles(["admin", "inventory_manager"])
async def cancel_maintenance_endpoint(maintenance_id: int, reason: Optional[str] = None, db: Session = Depends(get_db)):
    """Cancelar un mantenimiento"""
    try:
        maintenance = cancel_maintenance(db, maintenance_id, reason)
        if not maintenance:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mantenimiento no encontrado")
        return maintenance
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
@router.delete("/{maintenance_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_roles(["admin"])
async def delete_maintenance_endpoint(maintenance_id: int, db: Session = Depends(get_db)):
    """Eliminar un mantenimiento"""
    try: 
        success = delete_maintenance(db, maintenance_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mantenimiento no encontrado")
        return None
    except ValueError as e: 
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
@router.get("/asset/{asset_id}/history", response_model=List[AssetMaintenanceWithDetails])
async def get_asset_maintenance_history_endpoint(asset_id: int, db: Session = Depends(get_db)):
    """Obtener historial de mantenimiento de un activo especifico"""    
    from app.services.tech_asset_service import get_tech_asset

    # Verificar existencia del activo
    asset = get_tech_asset(db, asset_id)
    if not asset: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado")
    return get_asset_maintenance_history(db, asset_id)

@router.get("/upcoming/schedule", response_model=List[MaintenanceSchedule])
async def get_upcoming_schedule_endpoint(days_ahead: int = 30, db: Session = Depends(get_db)):
    """Obtener mantenimientos proximos agendados"""
    return get_upcoming_maintenances(db, days_ahead)

@router.get("/overdue/list", response_model=List[AssetMaintenanceWithDetails])
async def get_overdue_maintenances_endpoint(db: Session = Depends(get_db)):
    """Obtener mantenimientos vencidos"""
    return get_overdue_maintenances(db)

@router.get("/metrics/overview", response_model=MaintenanceMetrics)
async def get_maintenance_metrics_endpoint(date_from: Optional[datetime] = None, date_to: Optional[datetime] = None, db: Session = Depends(get_db)):
    """Obtener metricas de mantenimiento"""
    return get_maintenance_metrics(db, date_from, date_to)

@router.post("/asset/{asset_id}/schedule-preventive", response_model=AssetMaintenanceRead)
@require_roles(["admin", "invetory_manager"])
async def schedule_preventive_maintenance_endpoint(asset_id: int, maintenance_interval_days: int = 90, db: Session = Depends(get_db)):
    """Programar mantenimiento preventivo automatico"""
    try:
        maintenance = schedule_preventive_maintenance(db, asset_id,maintenance_interval_days)
        if not maintenance:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mantenimiento no encontrado")
        return maintenance
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    

@router.get("/types/list")
async def get_maintenance_types():
    """Obtener lista de tipos de mantenimiento"""
    return [
        {"value": mtype.value, "label": mtype.value.replace("_", " ").title()}
        for mtype in MaintenanceType
    ]


@router.get("/statuses/list")
async def get_maintenance_statuses():
    """Obtener lista de estados de mantenimiento"""
    return [
        {"value": status.value, "label": status.value.replace("_", " ").title()}
        for status in MaintenanceStatus
    ]

@router.get("/priorities/list")
async def get_maintenance_priorities():
    """Obtener lista de prioridades de mantenimiento"""
    return [
        {"value": priority.value, "label": priority.value.title()}
        for priority in MaintenancePriority
    ]