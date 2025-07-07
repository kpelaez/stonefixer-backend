from sqlmodel import Session, select
from datetime import datetime, timezone


from app.models.asset_maintenance import (
    AssetMaintenance,
    AssetMaintenanceCreate,
    AssetMaintenanceUpdate,
    AssetMaintenanceRead,
    AssetMaintenanceWithDetails,
    StartMaintenance,
    CompleteMaintenance,
    MaintenanceType,
    MaintenanceStatus,
    MaintenancePriority,
    MaintenanceSchedule,
    MaintenanceMetrics
)
from app.models.tech_asset import TechAsset, AssetStatus
from app.models.user import User

def creeate_maintenance(db: Session, maintenance: AssetMaintenanceCreate):
    """"Crear un nuevo registro de mantenimiento"""

    # Verificar que el activo existe
    tech_asset = db.get(TechAsset, maintenance.tech_asset_id)
    if not tech_asset:
        raise ValueError("El activo tecnologico no existe")
    
    # Verificar que el tecnico existe
    if maintenance.assigned_technician_id:
        technician = db.get(User, maintenance.assigned_technician_id)
        if not technician:
            raise ValueError("El tecnico asignado no existe")

    # Verificar que el usuario solicitante existe
    if maintenance.requested_by_user_id:
        requester = db.get(User, maintenance.requested_by_user_id)
        if not requester:
            raise ValueError("El usuario solicitante no existe")

    # Crear el mantenimiento
    db_maintenance = AssetMaintenance(**maintenance.model_dump())
    db_maintenance.created_at = datetime.now(timezone.utc)

    db.add(db_maintenance)
    db.commit()
    db.refresh(db_maintenance)

    return db_maintenance