from typing import Optional
from sqlmodel import Session, select
from datetime import datetime, timedelta, timezone


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

def create_maintenance(db: Session, maintenance: AssetMaintenanceCreate):
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
    db_maintenance = AssetMaintenance(**maintenance.dict())
    db_maintenance.created_at = datetime.now(timezone.utc)

    db.add(db_maintenance)
    db.commit()
    db.refresh(db_maintenance)

    return db_maintenance


def get_maintenance(db: Session, maintenance_id: int):
    """Obtener un mantenimiento por ID con detalles"""

    maintenance = db.get(AssetMaintenance, maintenance_id)
    if not maintenance:
        return None
    
    # Obtener detalles del activo y usuarios
    tech_asset = db.get(TechAsset, maintenance.tech_asset_id)
    
    requester = None
    if maintenance.requested_by_user_id:
        requester = db.get(User, maintenance.requested_by_user_id)

    # Crear una respuesta con detalles
    maintenance_data = AssetMaintenanceWithDetails.model_validate(maintenance)

    if tech_asset:
        maintenance_data.tech_asset_name = tech_asset.name
        maintenance_data.tech_asset_serial = tech_asset.serial_number
        maintenance_data.tech_asset_brand = tech_asset.brand
        maintenance_data.tech_asset_model = tech_asset.model

    if requester:
        maintenance_data.requested_by_name = requester.full_name

    # Calcular costo total
    total_cost = 0
    if maintenance.labor_cost:
        total_cost += maintenance.labor_cost
    if maintenance.parts_cost:
        total_cost += maintenance.parts_cost
    if maintenance.external_service_cost:
        total_cost += maintenance.external_service_cost
    
    maintenance_data.total_cost = total_cost if total_cost > 0 else None

    return maintenance_data


def get_maintenances(
        db: Session, 
        status: Optional[MaintenanceStatus] = None,
        maintenance_type: Optional[MaintenanceType] = None,
        priority: Optional[MaintenancePriority] = None,
        asset_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ):
    """Obtener listado de mantenimientos con filtros"""

    query = select(AssetMaintenance)

    # Aplicar filtros
    if status:
        query = query.where(AssetMaintenance.status == status)
    
    if maintenance_type:
        query = query.where(AssetMaintenance.maintenance_type == maintenance_type)

    if priority:
        query = query.where(AssetMaintenance.priority == priority)

    if asset_id:
        query = query.where(AssetMaintenance.tech_asset_id == asset_id)

    if date_from:
        query = query.where(AssetMaintenance.scheduled_date >= date_from)

    if date_to:
        query = query.where(AssetMaintenance.scheduled_date <= date_to)
    
    # Ordenar por fecha programada

    query = query.order_by(AssetMaintenance.scheduled_date.desc())

    maintenances = db.exec(query).all()

    # Convertir a AssetMaintenanceWithDetails
    detailed_maintenances = []
    for maintenance in maintenances:
        detailed_maintenance = get_maintenance(db, maintenance.id)
        if detailed_maintenance:
            detailed_maintenances.append(detailed_maintenance)

    return detailed_maintenances
    
def update_maintenance(db: Session, maintenance_id: int, maintenance_update: AssetMaintenanceUpdate):
    """Actualizar un mantenimiento"""

    maintenance = db.get(AssetMaintenance, maintenance_id)
    if not maintenance:
        return None
    
    # Obtener datos de actualizacion excluyendo campos no establecidos
    update_data = maintenance_update.dict(exclude_unset = True)

    # Actualizar campos
    for field, value in update_data.items():
        setattr(maintenance, field, value)
    
    maintenance.updated_at = datetime.now(timezone.utc)

    db.add(maintenance)
    db.commit()
    db.refresh(maintenance)

    return maintenance

def delete_maintenance(db: Session, maintenance_id: int):
    """Eliminar un mantenimiento"""

    maintenance = db.get(AssetMaintenance, maintenance_id)
    if not maintenance:
        return False
    
    # Solo permitir eliminar mantenimientos programados o cancelados
    if maintenance.status in [MaintenanceStatus.IN_PROGRESS, MaintenanceStatus.COMPLETED]:
        raise ValueError("No se pueden eliminar mantenimientos en progreso o completados")

    db.delete(maintenance)
    db.commit()

    return True


# GESTION DE MANTENIMIENTOS

def start_maintenance(db: Session, maintenance_id: int, start_data: StartMaintenance):
    """Iniciar un mantenimiento"""

    maintenance = db.get(AssetMaintenance, maintenance_id)
    if not maintenance:
        return None
    
    if maintenance.status != MaintenanceStatus.SCHEDULED:
        raise ValueError("Solo se pueden inciar mantenimientos programados")

    # Actualizar estado y fecha de inicio
    maintenance.status = MaintenanceStatus.IN_PROGRESS
    maintenance.started_at = start_data.started_at or datetime.now(timezone.utc)
    if start_data.notes:
        maintenance.notes = f"{maintenance.notes or ''}\n[INICIO] {start_data.notes}".strip()
    maintenance.updated_at = datetime.now(timezone.utc)

    # Actualizar estado del activo
    tech_asset = db.get(TechAsset, maintenance.tech_asset_id)
    if tech_asset:
        tech_asset.status = AssetStatus.IN_MAINTENANCE
        tech_asset.updated_at = datetime.now(timezone.utc)
        db.add(tech_asset)
    
    db.add(maintenance)
    db.commit()
    db.refresh(maintenance)

    return maintenance

def complete_maintenance(db: Session, maintenance_id: int, complete_data: CompleteMaintenance):
    """Completar un mantenimiento"""

    maintenance = db.get(AssetMaintenance, maintenance_id)
    if not maintenance:
        return None
    
    if maintenance.status != MaintenanceStatus.IN_PROGRESS:
        raise ValueError("Solo se pueden completar mantenimientos en progreso")

    # Actualizar datos de finalizacion
    maintenance.status = MaintenanceStatus.COMPLETED
    maintenance.completed_at = complete_data.completed_at or datetime.now(timezone.utc)

    # Actualizar informacion tecnica y costos
    if complete_data.procedures_performed:
        maintenance.procedures_performed = complete_data.procedures_performed

    if complete_data.parts_replaced:
        maintenance.parts_replaced = complete_data.parts_replaced
    
    if complete_data.tools_used:
        maintenance.tools_used = complete_data.tools_used

    if complete_data.labor_cost is not None:
        maintenance.parts_cost = complete_data.labor_cost
    
    if complete_data.parts_cost is not None:
        maintenance.parts_cost = complete_data.parts_cost
    
    if complete_data.external_service_cost is not None:
        maintenance.external_service_cost = complete_data.external_service_cost

    maintenance.follow_up_required = complete_data.follow_up_required
    if complete_data.follow_up_date:
        maintenance.follow_up_date = complete_data.follow_up_date
    
    if complete_data.notes:
        maintenance.notes = f"{maintenance.notes or ''}\n [COMPLETADO] {complete_data.notes}".strip()

    maintenance.updated_at = datetime.now(timezone.utc)

    # ACtualizar estado del activo (volver a disponible o asignado segun corresponda)
    tech_asset = db.get(TechAsset, maintenance.tech_asset_id)
    if tech_asset:
        # Verificar si el activo tiene asignaciones activa
        from app.models.asset_assignment import AssetAssignment, AssignmentStatus
        active_assignment = db.exec(
            select(AssetAssignment)
            .where(AssetAssignment.tech_asset_id == maintenance.tech_asset_id)
            .where(AssetAssignment.status == AssignmentStatus.ACTIVE)
        ).first()

        if active_assignment:
            tech_asset.status = AssetStatus.ASSIGNED
        else:
            tech_asset.status = AssetStatus.AVAILABLE

        tech_asset.updated_at = datetime.now(timezone.utc)
        db.add(tech_asset)

    db.add(maintenance)
    db.commit()
    db.refresh(maintenance)

    return maintenance

def cancel_maintenance(db: Session, maintenance_id: int, reason: Optional[str] = None):
    """Cancelar un mantenimiento"""

    maintenance = db.get(AssetMaintenance, maintenance_id)
    if not maintenance:
        return None
    
    if maintenance.status in [MaintenanceStatus.COMPLETED, MaintenanceStatus.CANCELED]:
        raise ValueError("No se puede cancelar un mantenimiento completado o ya cancelado")

    # Actualiar estado
    maintenance.status = MaintenanceStatus.CANCELED
    if reason: 
        maintenance.notes = f"{maintenance.notes or ''}\n[CANCELADO] {reason}".strip()
    
    maintenance.updated_at = datetime.now(timezone.utc)

    # Si estaba en progreso, actualizar estado del activo
    if maintenance.status == MaintenanceStatus.IN_PROGRESS:
        tech_asset = db.get(TechAsset, maintenance.tech_asset_id)
        if tech_asset and tech_asset.status == AssetStatus.IN_MAINTENANCE:
            # Verificar si tiene asignacion activa
            from app.models.asset_assignment import AssetAssignment, AssignmentStatus
            active_assignment = db.exec(
                select(AssetAssignment)
                .where(AssetAssignment.tech_asset_id == maintenance.tech_asset_id)
                .where(AssetAssignment.status == AssignmentStatus.ACTIVE)
            ).first()

            if active_assignment:
                tech_asset.status = AssetStatus.ASSIGNED
            else:
                tech_asset.status = AssetStatus.AVAILABLE

            tech_asset.updated_at = datetime.now(timezone.utc)
            db.add(tech_asset)

    db.add(maintenance)
    db.commit()
    db.refresh(maintenance)

    return maintenance


# OBTENER INFORMACION DE MANTENIMIENTOS

def get_asset_maintenance_history(db: Session, asset_id: int):
    """Obtener historial de mantenimiento de un activo especifico"""

    return get_maintenances(db=db, asset_id=asset_id)

def get_upcoming_maintenances(db: Session, days_ahead: int = 30):
    """Obtener mantenimientos proximos"""

    end_date = datetime.now(timezone.utc) + timedelta(days= days_ahead)

    maintenances = db.exec(
        select(AssetMaintenance, TechAsset, User)
        .join(TechAsset, AssetMaintenance.tech_asset_id == TechAsset.id)
        .where(AssetMaintenance.scheduled_date >= datetime.now(timezone.utc))
        .where(AssetMaintenance.scheduled_date <= end_date)
        .where(AssetMaintenance.status.in_([MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS]))
        .order_by(AssetMaintenance.scheduled_date)
    ).all()

    schedule = []

    for maintenance, tech_asset, in maintenances:
        schedule_item = MaintenanceSchedule(
            id = maintenance.id,
            title=maintenance.title,
            tech_asset_name=tech_asset.name,
            scheduled_date=maintenance.scheduled_date,
            estimated_duration_hours=maintenance.estimated_duration_hours,
            priority=maintenance.priority,
            status=maintenance.status,
        )
        schedule.append(schedule_item)

    return schedule

def get_overdue_maintenances(db: Session):
    """Obtener mantenimientos vencidos"""

    return get_maintenances(db=db, status=MaintenanceStatus.SCHEDULED, date_to=datetime.now(timezone.utc))

def get_maintenance_metrics(db: Session, date_from: Optional[datetime]= None, date_to: Optional[datetime]= None):
    """Obtener metricas de mantenimiento"""

    query = select(AssetMaintenance)

    if date_from:
        query = query.where(AssetMaintenance.scheduled_date >= date_from)
    
    if date_to:
        query = query.where(AssetMaintenance.scheduled_date <= date_to)

    maintenances = db.exec(query).all()

    total_maintenances = len(maintenances)
    completed_maintenances = len([m for m in maintenances if m.status == MaintenanceStatus.COMPLETED])
    pending_maintenances = len([m for m in maintenances if m.status in [
        MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS
    ]])
    
    # Mantenimientos vencidos
    now = datetime.utcnow()
    overdue_maintenances = len([
        m for m in maintenances 
        if m.status == MaintenanceStatus.SCHEDULED and m.scheduled_date < now
    ])
    
    # Tiempo promedio de finalización
    completed_with_times = [
        m for m in maintenances 
        if m.status == MaintenanceStatus.COMPLETED and m.started_at and m.completed_at
    ]
    
    average_completion_time_hours = None
    if completed_with_times:
        total_hours = sum([
            (m.completed_at - m.started_at).total_seconds() / 3600
            for m in completed_with_times
        ])
        average_completion_time_hours = total_hours / len(completed_with_times)
    
    # Costo total de mantenimiento
    total_maintenance_cost = 0
    for m in maintenances:
        if m.labor_cost:
            total_maintenance_cost += m.labor_cost
        if m.parts_cost:
            total_maintenance_cost += m.parts_cost
        if m.external_service_cost:
            total_maintenance_cost += m.external_service_cost
    
    # Ratio preventivo vs correctivo
    preventive_count = len([m for m in maintenances if m.maintenance_type == MaintenanceType.PREVENTIVE])
    corrective_count = len([m for m in maintenances if m.maintenance_type == MaintenanceType.CORRECTIVE])
    
    preventive_vs_corrective_ratio = None
    if corrective_count > 0:
        preventive_vs_corrective_ratio = preventive_count / corrective_count
    
    return MaintenanceMetrics(
        total_maintenances=total_maintenances,
        completed_maintenances=completed_maintenances,
        pending_maintenances=pending_maintenances,
        overdue_maintenances=overdue_maintenances,
        average_completion_time_hours=average_completion_time_hours,
        total_maintenance_cost=total_maintenance_cost if total_maintenance_cost > 0 else None,
        preventive_vs_corrective_ratio=preventive_vs_corrective_ratio
    )

def schedule_preventive_maintenance(db: Session, asset_id: int, maintenance_interval_days: int = 90):
    """Programar mantenimiento preventivo automático"""
    
    tech_asset = db.get(TechAsset, asset_id)
    if not tech_asset:
        raise ValueError("El activo tecnológico no existe")
    
    # Calcular próxima fecha de mantenimiento
    last_maintenance = db.exec(
        select(AssetMaintenance)
        .where(AssetMaintenance.tech_asset_id == asset_id)
        .where(AssetMaintenance.maintenance_type == MaintenanceType.PREVENTIVE)
        .where(AssetMaintenance.status == MaintenanceStatus.COMPLETED)
        .order_by(AssetMaintenance.completed_at.desc())
    ).first()
    
    if last_maintenance and last_maintenance.completed_at:
        next_date = last_maintenance.completed_at + timedelta(days=maintenance_interval_days)
    else:
        next_date = datetime.now(timezone.utc) + timedelta(days=maintenance_interval_days)
    
    # Crear mantenimiento preventivo
    preventive_maintenance = AssetMaintenanceCreate(
        tech_asset_id=asset_id,
        maintenance_type=MaintenanceType.PREVENTIVE,
        title=f"Mantenimiento Preventivo - {tech_asset.name}",
        description=f"Mantenimiento preventivo programado para {tech_asset.name} ({tech_asset.serial_number})",
        priority=MaintenancePriority.MEDIUM,
        scheduled_date=next_date,
        estimated_duration_hours=2.0
    )
    
    return create_maintenance(db, preventive_maintenance)