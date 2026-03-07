from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Integer, Session, select, func
from datetime import date as date_type, datetime, timedelta
from typing import List, Optional

from app.db.database import get_db
from app.models.role import UserRole
from app.models.shift_schedule import (
    ShiftSchedule, ShiftScheduleCreate, ShiftScheduleUpdate, 
    ShiftScheduleRead, ShiftScheduleStats, ShiftType, ShiftStatus
)
from app.models.user import User
from app.api.deps import get_current_user, require_roles, get_user_roles
from app.services.shift_schedule_service import ShiftScheduleService

router = APIRouter()

def get_user_roles_list(user_id: int, db: Session) -> list[str]:
    """Helper para obtener roles del usuario"""
    user_roles = db.exec(
        select(UserRole.role).where(UserRole.user_id == user_id)
    ).all()
    return list(user_roles)

@router.get("/", response_model=List[ShiftScheduleRead])
def get_shift_schedules(
    start_date: date_type = Query(..., description="Fecha de inicio"),
    end_date: date_type = Query(..., description="Fecha de fin"),
    department: str = Query("stock", description="Departamento"),
    user_id: Optional[int] = Query(None, description="Filtrar por usuario"),
    shift_type: Optional[ShiftType] = Query(None, description="Filtrar por tipo de turno"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener turnos en un rango de fechas
    Público para todos los usuarios del departamento
    """
    query = select(ShiftSchedule).where(
        ShiftSchedule.date >= start_date,
        ShiftSchedule.date <= end_date,
        ShiftSchedule.department == department,
        ShiftSchedule.status == ShiftStatus.CONFIRMED
    )
    
    if user_id:
        query = query.where(ShiftSchedule.user_id == user_id)
    
    if shift_type:
        query = query.where(ShiftSchedule.shift_type == shift_type)
    
    shifts = db.exec(query).all()
    
    # Enriquecer con datos del usuario
    result = []
    for shift in shifts:
        shift_dict = shift.dict()
        shift_dict["user_full_name"] = shift.user.full_name
        shift_dict["user_email"] = shift.user.email
        
        if shift.modified_by:
            shift_dict["modified_by_full_name"] = shift.modified_by.full_name
        
        result.append(ShiftScheduleRead(**shift_dict))
    
    return result


@router.post("/", response_model=ShiftScheduleRead, status_code=201)
def create_shift_schedule(
    shift_data: ShiftScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crear un nuevo turno (usuario se auto-asigna)
    """
    # Validaciones
    ShiftScheduleService.validate_date(shift_data.date)
    
    ShiftScheduleService.validate_early_shift_capacity(
        db, shift_data.date, shift_data.shift_type
    )
    
    ShiftScheduleService.validate_duplicate_assignment(
        db, current_user.id, shift_data.date
    )
    
    # Crear turno
    new_shift = ShiftSchedule(
        **shift_data.dict(),
        user_id=current_user.id,
        department="stock"  # Hardcoded por ahora
    )
    
    db.add(new_shift)
    db.commit()
    db.refresh(new_shift)
    
    # Enriquecer respuesta
    result_dict = new_shift.dict()
    result_dict["user_full_name"] = new_shift.user.full_name
    result_dict["user_email"] = new_shift.user.email
    
    return ShiftScheduleRead(**result_dict)


@router.patch("/{shift_id}", response_model=ShiftScheduleRead)
def update_shift_schedule(
    shift_id: int,
    shift_data: ShiftScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Actualizar un turno existente
    - Usuarios pueden modificar sus propios turnos (respetando deadline)
    - Supervisores pueden modificar cualquier turno
    """
    # Buscar turno
    shift = db.get(ShiftSchedule, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    
    # Obtener roles del usuario actual
    user_roles = get_user_roles_list(current_user.id, db)

    # Validar deadline
    ShiftScheduleService.validate_modification_deadline(
        shift.date,
        current_user.id,
        shift.user_id,
        user_roles
    )
    
    # Si cambia la fecha, validar nueva fecha
    if shift_data.date and shift_data.date != shift.date:
        ShiftScheduleService.validate_date(shift_data.date)
        ShiftScheduleService.validate_duplicate_assignment(
            db, shift.user_id, shift_data.date, exclude_shift_id=shift_id
        )
    
    # Si cambia a early, validar capacidad
    if shift_data.shift_type == ShiftType.EARLY:
        target_date = shift_data.date if shift_data.date else shift.date
        ShiftScheduleService.validate_early_shift_capacity(
            db, target_date, ShiftType.EARLY, exclude_shift_id=shift_id
        )
    
    # Actualizar campos
    if shift_data.date is not None:
        shift.date = shift_data.date
    if shift_data.shift_type is not None:
        shift.shift_type = shift_data.shift_type
    if shift_data.status is not None:
        shift.status = shift_data.status
    if shift_data.notes is not None:
        shift.notes = shift_data.notes
    
    # Auditoría
    is_supervisor = any(role in ["admin", "manager"] for role in user_roles)
    if is_supervisor and current_user.id != shift.user_id:
        shift.modified_by_user_id = current_user.id
    
    shift.updated_at = datetime.now()
    
    db.add(shift)
    db.commit()
    db.refresh(shift)
    
    # Respuesta
    result_dict = {
        "id": shift.id,
        "user_id": shift.user_id,
        "department": shift.department,
        "date": shift.date,
        "shift_type": shift.shift_type,
        "status": shift.status,
        "notes": shift.notes,
        "created_at": shift.created_at,
        "updated_at": shift.updated_at,
        "user_full_name": shift.user.full_name,
        "user_email": shift.user.email,
        "modified_by_user_id": shift.modified_by_user_id,
        "modified_by_full_name": shift.modified_by.full_name if shift.modified_by else None
    }
    
    return ShiftScheduleRead(**result_dict)


@router.delete("/{shift_id}", status_code=204)
def delete_shift_schedule(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Eliminar (cancelar) un turno
    - Usuarios pueden cancelar sus propios turnos (respetando deadline)
    - Supervisores pueden cancelar cualquier turno
    """
    shift = db.get(ShiftSchedule, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    
    # Obtener roles del usuario actual
    user_roles = get_user_roles_list(current_user.id, db)
        
    # Validar deadline
    ShiftScheduleService.validate_modification_deadline(
        shift.date,
        current_user.id,
        shift.user_id,
        user_roles
    )
    
    # En lugar de eliminar, marcar como cancelado
    shift.status = ShiftStatus.CANCELLED
    shift.updated_at = datetime.now()
    
    is_supervisor = any(role in ["admin", "manager"] for role in user_roles)
    if is_supervisor and current_user.id != shift.user_id:
        shift.modified_by_user_id = current_user.id
    
    db.add(shift)
    db.commit()
    
    return None


# === ENDPOINTS DE ESTADÍSTICAS ===

@router.get("/stats", response_model=List[ShiftScheduleStats])
def get_shift_statistics(
    start_date: date_type = Query(..., description="Fecha de inicio"),
    end_date: date_type = Query(..., description="Fecha de fin"),
    department: str = Query("stock", description="Departamento"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener estadísticas de turnos por usuario en un período
    """
    # Query para contar turnos por usuario y tipo
    stats_query = (
        select(
            ShiftSchedule.user_id,
            User.full_name,
            func.count(ShiftSchedule.id).label("total_shifts"),
            func.sum(
                func.cast(ShiftSchedule.shift_type == ShiftType.EARLY, Integer)
            ).label("early_shifts"),
            func.sum(
                func.cast(ShiftSchedule.shift_type == ShiftType.REGULAR, Integer)
            ).label("regular_shifts")
        )
        .join(User, ShiftSchedule.user_id == User.id)
        .where(
            ShiftSchedule.date >= start_date,
            ShiftSchedule.date <= end_date,
            ShiftSchedule.department == department,
            ShiftSchedule.status == ShiftStatus.CONFIRMED
        )
        .group_by(ShiftSchedule.user_id, User.full_name)
    )
    
    results = db.exec(stats_query).all()
    
    # Calcular total de turnos del equipo
    total_team_shifts = sum(r.total_shifts for r in results)
    
    # Construir respuesta
    stats = []
    for r in results:
        stats.append(ShiftScheduleStats(
            user_id=r.user_id,
            user_full_name=r.full_name,
            total_shifts=r.total_shifts,
            early_shifts=r.early_shifts or 0,
            regular_shifts=r.regular_shifts or 0,
            percentage_of_total=(r.total_shifts / total_team_shifts * 100) if total_team_shifts > 0 else 0
        ))
    
    return stats


@router.get("/alerts")
def get_shift_alerts(
    department: str = Query("stock", description="Departamento"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener alertas de turnos sin asignar
    """
    alerts = ShiftScheduleService.check_unassigned_alerts(db, department)
    return {"alerts": alerts, "count": len(alerts)}
