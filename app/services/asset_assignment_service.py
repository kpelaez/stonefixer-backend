from typing import List, Optional
from sqlmodel import Session, select
from datetime import datetime, timezone

from app.models.asset_assignment import (
    AssetAssignment,
    AssetAssignmentCreate,
    AssetAssignmentRead,
    AssetAssignmentUpdate,
    AssetAssignmentWithDetails,
    AssetReturn,
    AssignmentStatus,
    UserAssignmentSummary
)

from app.models.tech_asset import TechAsset, AssetStatus
from app.models.user import User

def create_assignment(db: Session, assignment: AssetAssignmentCreate, assigned_by_user_id: Optional[int] = None):
    """Crear una nueva asignacion de activo"""

    # Verificar que el activo existe y esta disponible
    tech_asset = db.get(TechAsset, assignment.tech_asset_id)
    if not tech_asset:
        raise ValueError("El activo tecnologico no existe")

    if tech_asset.status != AssetStatus.AVAILABLE:
        raise ValueError(f"EL actino no esta disponible para asignacion. Estado actual: {tech_asset.status}")
    
    # Verificar que el usuario existe
    user = db.get(User, assignment.assigned_to_user_id)
    if not user:
        raise ValueError("El usuario no existe")
    
    # Verificar si hay alguna asignacion activa para este activo
    existing_assignment = db.exec(
        select(AssetAssignment)
        .where(AssetAssignment.tech_asset_id == assignment.tech_asset_id)
        .where(AssetAssignment.status == AssignmentStatus.ACTIVE)
    ).first()

    if existing_assignment:
        raise ValueError("El activo ya tiene una asignacion activa")
    
    # Crear la asignacion
    db_assignment = AssetAssignment(**assignment.model_dump())
    db_assignment.assigned_by_user_id = assigned_by_user_id
    db_assignment.created_at = datetime.now(timezone.utc)

    # Actualizar el estado del activo
    tech_asset.status = AssetStatus.ASSIGNED
    tech_asset.updated_at = datetime.now(timezone.utc)

    db.add(db_assignment)
    db.add(tech_asset)
    db.commit()
    db.refresh(db_assignment)

    return db_assignment

def get_assignment(db: Session, assignment_id: int):
    """Obtener una asignacion por ID con detalles"""

    assignment = db.get(AssetAssignment, assignment_id)
    if not assignment:
        return None
    
    # Obtener detalles del activo y usuarios
    tech_asset = db.get(TechAsset, assignment.tech_asset_id)
    assigned_to_user = db.get(User, assignment.assigned_to_user_id)
    assigned_by_user = None
    if assignment.assigned_by_user_id:
        assigned_by_user = db.get(User, assignment.assigned_by_user_id)

    # Crear respuesta con detalles
    assignment_data = AssetAssignmentWithDetails.model_validate(assignment)

    if tech_asset:
        assignment_data.tech_asset_name = tech_asset.name
        assignment_data.tech_asset_serial = tech_asset.serial_number
        assignment_data.tech_asset_brand = tech_asset.brand
        assignment_data.tech_asset_model = tech_asset.model

    if assigned_to_user:
        assignment_data.assigned_to_name = assigned_to_user.full_name
        assignment_data.assigned_to_email = assigned_to_user.email

    if assigned_by_user:
        assignment_data.assigned_by_name = assigned_by_user.full_name

    return assignment_data


def get_assignments(db: Session, user_id: Optional[int] = None, asset_id: Optional[int]= None, active_only: bool = False):
    """Obtener lista de asignaciones con filtros"""
    
    query = select(AssetAssignment)

    # Aplicar Filtros
    if user_id:
        query = query.where(AssetAssignment.assigned_to_user_id == user_id)
    
    if asset_id:
        query = query.where(AssetAssignment.tech_asset_id == asset_id)
    
    if active_only:
        query = query.where(AssetAssignment.status == AssignmentStatus.ACTIVE)
    
    # Ordenar por fecha de asignación (más recientes primero)
    query = query.order_by(AssetAssignment.assigned_date.desc())
    
    assignments = db.exec(query).all()
    
    # Convertir a AssetAssignmentWithDetails
    detailed_assignments = []
    for assignment in assignments:
        detailed_assignment = get_assignment(db, assignment.id)
        if detailed_assignment:
            detailed_assignments.append(detailed_assignment)
    
    return detailed_assignments

def update_assignment(db: Session, assignment_id: int, assignment_update: AssetAssignment):
    """Actualizar una asignacion"""

    assignment = db.get(AssetAssignment, assignment_id)
    if not assignment:
        return None
    
    # Obtener datos de actualizacion excluyendo campos no establecidos
    update_data = assignment_update.model_dump(exclude_unset = True)

    # Actualizar campos
    for field, value in update_data.items():
        setattr(assignment, field, value)

        assignment.updated_at = datetime.now(timezone.utc)

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return assignment

def return_asset(db: Session, assignment_id: int, return_data: AssetReturn):
    """Marcar un activo como devuelto"""

    assignment = db.get(AssetAssignment, assignment_id)
    if not assignment:
        return None
    
    if assignment.status != AssignmentStatus.ACTIVE:
        raise ValueError("Solo se pueden devolver asignaciones activas")
    
    # Actualizar el estado del activo
    tech_asset = db.get(TechAsset, assignment.tech_asset_id)
    if tech_asset:
        if return_data.status == AssignmentStatus.RETURNED:
            tech_asset.status = AssetStatus.AVAILABLE
        elif return_data.status == AssignmentStatus.DAMAGED:
            tech_asset.status = AssetStatus.OUT_OF_ORDER
        elif return_data.status == AssignmentStatus.LOST:
            tech_asset.status = AssetStatus.RETIRED

        tech_asset.updated_at = datetime.now(timezone.utc)
        db.add(assignment)
        db.commit()
        db.refresh(assignment)

    return assignment

def transfer_asset(db: Session, assignmet_id: int, new_user_id: int, transfer_notes:Optional[str] = None):
    """Transferir un activo de un usuario a otro"""

    # Marcar la asignacion actual como transferida
    current_assignment = db.get(AssetAssignment, assignmet_id)
    if not current_assignment:
        raise ValueError("La asignacion no existe")
    
    if current_assignment.status != AssignmentStatus.ACTIVE:
        raise ValueError("Solo se pueden transferir asignaciones activas")

    # Verificar que el nuevo usuario existe
    new_user = db.get(User, new_user_id)
    if not new_user:
        raise ValueError("El usuario destino no existe")
    
    # Marcar asignacion actual como transferida
    current_assignment.status = AssignmentStatus.TRANSFERED
    current_assignment.actual_return_date = datetime.now(timezone.utc)
    current_assignment.return_notes = transfer_notes
    current_assignment.updated_at = datetime.now(timezone.utc)

    # Crear nueva asignacion
    new_assignment_data = AssetAssignmentCreate(
        tech_asset_id= current_assignment.tech_asset_id,
        assigned_to_user_id=new_user_id,
        assignment_reason="Transferencia de activo",
        assignment_notes=f"Transferido desde usuadio ID: {current_assignment.assigned_to_user_id}"
    )

    # El activo ya esta asignado, asi que no verificamos disponibilidad
    new_assignment = AssetAssignment(**new_assignment_data.model_dump())
    new_assignment.created_at = datetime.now(timezone.utc)

    db.add(current_assignment)
    db.add(new_assignment)
    db.commit()
    db.refresh(new_assignment)

    return new_assignment

def delete_assignmet(db: Session, assignment_id: int):
    """Eliminar/descativar una asignacion (marcar como devuelta)"""

    assignmet = db.get(AssetAssignment, assignment_id)
    if not assignmet:
        return False
    
    if assignmet.status == AssignmentStatus.ACTIVE:
        # Si esta activa, marcarla como devuelta
        return_data = AssetReturn(
            actual_return_date=datetime.now(timezone.utc),
            status=AssignmentStatus.RETURNED,
            return_notes="Asignacion terminada administrativamente"
        )
        return_asset(db, assignment_id, return_data)
    
    return True

def get_user_assignments(db: Session, user_id: int, active_only: bool = True):
    """Obtener asignaciones de un usuario especifico"""

    return get_assignments(db, user_id, active_only)

def get_asset_assignments(db: Session, asset_id: int):
    """Obtener historial de asignaciones de un activo especifico"""

    return get_assignments(db, asset_id)


def get_assignment_statistics(db: Session) -> dict:
    """Obtener estadísticas de asignaciones"""
    
    # Contar total de asignaciones
    total_assignments = db.exec(select(AssetAssignment)).count()
    
    # Contar por estado
    status_counts = {}
    for status in AssignmentStatus:
        count = db.exec(
            select(AssetAssignment).where(AssetAssignment.status == status)
        ).count()
        status_counts[status.value] = count
    
    # Asignaciones activas
    active_assignments = status_counts.get(AssignmentStatus.ACTIVE.value, 0)
    
    # Usuarios con asignaciones activas
    users_with_assignments = db.exec(
        select(AssetAssignment.assigned_to_user_id)
        .where(AssetAssignment.status == AssignmentStatus.ACTIVE)
        .distinct()
    ).all()
    
    return {
        "total_assignments": total_assignments,
        "active_assignments": active_assignments,
        "status_distribution": status_counts,
        "users_with_active_assignments": len(users_with_assignments)
    }



def get_users_assignment_summary(db: Session) -> List[UserAssignmentSummary]:
    """Obtener resumen de asignaciones por usuario"""
    
    # Obtener usuarios con asignaciones
    users_with_assignments = db.exec(
        select(AssetAssignment.assigned_to_user_id)
        .distinct()
    ).all()
    
    summaries = []
    for user_id in users_with_assignments:
        user = db.get(User, user_id)
        if not user:
            continue
        
        # Contar asignaciones del usuario
        total_assignments = db.exec(
            select(AssetAssignment)
            .where(AssetAssignment.assigned_to_user_id == user_id)
        ).count()
        
        active_assignments = db.exec(
            select(AssetAssignment)
            .where(AssetAssignment.assigned_to_user_id == user_id)
            .where(AssetAssignment.status == AssignmentStatus.ACTIVE)
        ).count()
        
        # Obtener nombres de activos en posesión
        active_assets = db.exec(
            select(AssetAssignment, TechAsset)
            .join(TechAsset, AssetAssignment.tech_asset_id == TechAsset.id)
            .where(AssetAssignment.assigned_to_user_id == user_id)
            .where(AssetAssignment.status == AssignmentStatus.ACTIVE)
        ).all()
        
        assets_in_possession = [f"{asset.name} ({asset.serial_number})" for _, asset in active_assets]
        
        summary = UserAssignmentSummary(
            user_id=user.id,
            user_name=user.full_name,
            user_email=user.email,
            active_assignments=active_assignments,
            total_assignments=total_assignments,
            assets_in_possession=assets_in_possession
        )
        
        summaries.append(summary)
    
    return sorted(summaries, key=lambda x: x.active_assignments, reverse=True)