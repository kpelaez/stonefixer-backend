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

def create_assignment(db: Session, assignment_data: AssetAssignmentCreate, assigned_by_user_id: Optional[int] = None, is_transfer: bool = False):
    """Crear una nueva asignacion de activo"""

    # Verificar que el activo existe y esta disponible
    tech_asset = db.get(TechAsset, assignment_data.tech_asset_id)
    if not tech_asset:
        raise ValueError("El activo tecnologico no existe")
    
    # # MEJORADO: Validación de estado según contexto
    # if is_transfer:
    #     # En transferencias, el asset DEBE estar ASSIGNED
    #     if tech_asset.status != AssetStatus.ASSIGNED:
    #         raise ValueError(f"En transferencias, el activo debe estar asignado. Estado actual: {tech_asset.status}")
    # else:
    #     # En asignaciones normales, el asset DEBE estar AVAILABLE
    #     if tech_asset.status != AssetStatus.AVAILABLE:
    #         raise ValueError(f"El activo no está disponible para asignación. Estado actual: {tech_asset.status}")
    
    # Verificar que el usuario existe
    user = db.get(User, assignment_data.assigned_to_user_id)
    if not user:
        raise ValueError("El usuario no existe")
    
    if not user.is_active:
        raise ValueError("El usuario no está activo")
    
     # MEJORADO: Solo verificar asignaciones activas si NO es transferencia
    if not is_transfer:
        existing_assignment = db.exec(
            select(AssetAssignment)
            .where(AssetAssignment.tech_asset_id == assignment_data.tech_asset_id)
            .where(AssetAssignment.status == AssignmentStatus.ACTIVE)
        ).first()

        if existing_assignment:
            raise ValueError("El activo ya tiene una asignación activa")
    
    assignment_dict = assignment_data.dict(exclude_unset=True)

    # Convertir expected_return_date de string a datetime si viene como string
    if assignment_dict.get('expected_return_date'):
        try:
            assignment_dict['expected_return_date'] = datetime.fromisoformat(
                assignment_dict['expected_return_date'].replace('Z', '+00:00')
            )
        except (ValueError, AttributeError):
            # Si no es un string válido, establecer como None
            assignment_dict['expected_return_date'] = None
    
    # Crear la asignacion
    db_assignment = AssetAssignment(
        tech_asset_id=assignment_data.tech_asset_id,
        assigned_to_user_id=assignment_data.assigned_to_user_id,
        expected_return_date=assignment_dict.get('expected_return_date'),
        assignment_reason=assignment_data.assignment_reason,
        location_of_use=assignment_data.location_of_use,
        condition_at_assignment=assignment_data.condition_at_assignment or "good",
        assignment_notes=assignment_data.assignment_notes,
        assigned_by_user_id=assigned_by_user_id,
        assigned_date=datetime.now(timezone.utc),
        status=AssignmentStatus.ACTIVE
    )

    db.add(db_assignment)

    # MEJORADO: Solo actualizar estado si NO es transferencia
    # (en transferencias ya está ASSIGNED)
    if not is_transfer:
        tech_asset.status = AssetStatus.ASSIGNED
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
    assigned_by_user = db.get(User, assignment.assigned_by_user_id) if assignment.assigned_by_user_id else None

    # Crear respuesta con detalles
    return AssetAssignmentWithDetails(
        **assignment.dict(),
        tech_asset_name=tech_asset.name if tech_asset else None,
        tech_asset_serial=tech_asset.serial_number if tech_asset else None,
        tech_asset_brand=tech_asset.brand if tech_asset else None,
        tech_asset_model=tech_asset.model if tech_asset else None,
        tech_asset_asset_tag=tech_asset.asset_tag if tech_asset else None,
        assigned_to_name=assigned_to_user.full_name if assigned_to_user else None,
        assigned_to_email=assigned_to_user.email if assigned_to_user else None,
        assigned_by_name=assigned_by_user.full_name if assigned_by_user else None
    )


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
    query = query.order_by(AssetAssignment.created_at.desc())
    assignments = db.exec(query).all()
    
    # Convertir a AssetAssignmentWithDetails
    result = []
    for assignment in assignments:
        # Obtener detalles del activo
        tech_asset = db.get(TechAsset, assignment.tech_asset_id)
        assigned_to_user = db.get(User, assignment.assigned_to_user_id)
        assigned_by_user = db.get(User, assignment.assigned_by_user_id) if assignment.assigned_by_user_id else None

        assignment_detail = AssetAssignmentWithDetails(
            **assignment.dict(),
            tech_asset_name=tech_asset.name if tech_asset else None,
            tech_asset_serial=tech_asset.serial_number if tech_asset else None,
            tech_asset_brand=tech_asset.brand if tech_asset else None,
            tech_asset_model=tech_asset.model if tech_asset else None,
            tech_asset_asset_tag=tech_asset.asset_tag if tech_asset else None,
            assigned_to_name=assigned_to_user.full_name if assigned_to_user else None,
            assigned_to_email=assigned_to_user.email if assigned_to_user else None,
            assigned_by_name=assigned_by_user.full_name if assigned_by_user else None
        )
        result.append(assignment_detail)

    return result

def update_assignment(db: Session, assignment_id: int, assignment_update: AssetAssignment):
    """Actualizar una asignacion"""

    assignment = db.get(AssetAssignment, assignment_id)
    if not assignment:
        return None
    
    # Obtener datos de actualizacion excluyendo campos no establecidos
    update_data = assignment_update.dict(exclude_unset = True)

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
    
    # CORREGIDO: Actualizar TODOS los campos de la devolución
    assignment.status = AssignmentStatus.RETURNED
    assignment.actual_return_date = return_data.actual_return_date or datetime.now(timezone.utc)
    assignment.condition_at_return = return_data.condition_at_return
    assignment.return_notes = return_data.return_notes
    assignment.updated_at = datetime.now(timezone.utc)
    
    # Actualizar el estado del activo
    tech_asset = db.get(TechAsset, assignment.tech_asset_id)
    if tech_asset:
        tech_asset.status = AssetStatus.AVAILABLE

    db.add(assignment)
    if tech_asset:
        db.add(tech_asset)
    
    db.commit()
    db.refresh(assignment)

    return assignment

def transfer_asset(db: Session, assignmet_id: int, new_user_id: int, transfer_notes: Optional[str] = None):
    """Transferir un activo de un usuario a otro"""

    # Obtener la asignacion actual
    current_assignment = db.get(AssetAssignment, assignmet_id)
    if not current_assignment:
        raise ValueError("La asignacion no existe")
    
    if current_assignment.status != AssignmentStatus.ACTIVE:
        raise ValueError("Solo se pueden transferir asignaciones activas")

    # Verificar que el nuevo usuario existe y esta activo
    new_user = db.get(User, new_user_id)
    if not new_user or not new_user.is_active:
        raise ValueError("El usuario destino no existe")
    
    # NUEVO: Validar que no se transfiera al mismo usuario
    if current_assignment.assigned_to_user_id == new_user_id:
        raise ValueError("No se puede transferir un activo al mismo usuario que ya lo tiene asignado")
    
    # Liberar el asset ANTES de crear la nueva asignación
    tech_asset = db.get(TechAsset, current_assignment.tech_asset_id)
    if tech_asset:
        tech_asset.status = AssetStatus.AVAILABLE
        db.add(tech_asset)
        db.flush()  # Aplicar cambio sin hacer commit completo
    
    # Marcar asignacion actual como transferida
    current_assignment.status = AssignmentStatus.TRANSFERED
    current_assignment.actual_return_date = datetime.now(timezone.utc)
    current_assignment.return_notes = f"Transferido a  {new_user.full_name}. {transfer_notes or ''}"
    current_assignment.updated_at = datetime.now(timezone.utc)
    db.add(current_assignment)

    db.commit()
    db.refresh(current_assignment)

    # Crear nueva asignacion
    new_assignment_data = AssetAssignmentCreate(
        tech_asset_id=current_assignment.tech_asset_id,
        assigned_to_user_id=new_user_id,
        assignment_reason="transfer",
        location_of_use=current_assignment.location_of_use,
        condition_at_assignment=current_assignment.condition_at_assignment,
        assignment_notes=f"Transferido desde {current_assignment.assigned_to_user.full_name if current_assignment.assigned_to_user else 'usuario anterior'}. {transfer_notes or ''}"
    )

    new_assignment = create_assignment(db, new_assignment_data, current_assignment.assigned_by_user_id, is_transfer=True)

    return new_assignment


def delete_assignment(db: Session, assignment_id: int):
    """Eliminar/descativar una asignacion (marcar como devuelta)"""

    assignment = db.get(AssetAssignment, assignment_id)
    if not assignment:
        return False
    
    # CORREGIDO: Validar estado ANTES de actualizar
    if assignment.status == AssignmentStatus.ACTIVE:
        # Liberar el activo si estaba asignado
        tech_asset = db.get(TechAsset, assignment.tech_asset_id)
        if tech_asset:
            tech_asset.status = AssetStatus.AVAILABLE
            db.add(tech_asset)
    
    # Marcar como cancelada en lugar de eliminar
    assignment.status = AssignmentStatus.CANCELED
    assignment.updated_at = datetime.now(timezone.utc)

    # Liberar el activo si estaba asignado
    if assignment.status == AssignmentStatus.ACTIVE:
        tech_asset = db.get(TechAsset, assignment.tech_asset_id)
        if tech_asset:
            tech_asset.status = AssetStatus.AVAILABLE
            db.add(tech_asset)

    db.add(assignment)
    db.commit()

    return True

def get_user_assignments(db: Session, user_id: int, active_only: bool = True):
    """Obtener asignaciones de un usuario especifico"""

    return get_assignments(db, user_id=user_id, active_only=active_only)

def get_asset_assignments(db: Session, asset_id: int):
    """Obtener historial de asignaciones de un activo especifico"""

    return get_assignments(db, user_id=None ,asset_id=asset_id)


def get_assignment_statistics(db: Session) -> dict:
    """Obtener estadísticas de asignaciones"""
    
    # Contar total de asignaciones
    total_assignments = db.exec(select(AssetAssignment)).all()
    active_assignments = db.exec(
        select(AssetAssignment).where(AssetAssignment.status == AssignmentStatus.ACTIVE)
    ).all()

    return {
        "total_assignments": len(total_assignments),
        "active_assignments": len(active_assignments),
        "returned_assignments": len([a for a in total_assignments if a.status == AssignmentStatus.RETURNED]),
        "transfered_assignments": len([a for a in total_assignments if a.status == AssignmentStatus.TRANSFERED]),
        "canceled_assignments": len([a for a in total_assignments if a.status == AssignmentStatus.CANCELED])
    }



def get_users_assignment_summary(db: Session) -> List[UserAssignmentSummary]:
    """Obtener resumen de asignaciones por usuario"""
    users = db.exec(select(User).where(User.is_active == True)).all()
    result = []

    for user in users:
        user_assignments = db.exec(
            select(AssetAssignment).where(AssetAssignment.assigned_to_user_id == user.id)
        ).all()

        active_assignments = [a for a in user_assignments if a.status == AssignmentStatus.ACTIVE]
        
        assets_in_possession = []
        for assignment in active_assignments:
            tech_asset = db.get(TechAsset, assignment.tech_asset_id)
            if tech_asset:
                assets_in_possession.append(f"{tech_asset.name} ({tech_asset.asset_tag or 'Sin etiqueta'})")

        summary = UserAssignmentSummary(
            user_id=user.id,
            user_name=user.full_name,
            user_email=user.email,
            active_assignments=len(active_assignments),
            total_assignments=len(user_assignments),
            assets_in_possession=assets_in_possession
        )
        result.append(summary)

    return result