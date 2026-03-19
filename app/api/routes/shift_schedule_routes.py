from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Integer, Session, col, select, func, text
from datetime import date as date_type, datetime, timedelta
from typing import List, Optional
import logging

from app.db.database import get_db
from app.models.role import UserRole
from app.models.shift_schedule import (
    ShiftSchedule, ShiftScheduleCreate, ShiftScheduleUpdate, 
    ShiftScheduleRead, ShiftScheduleStats, ShiftType, ShiftStatus
)
from app.models.user import User
from app.api.deps import get_current_user, get_user_roles
from app.services.shift_schedule_service import ShiftScheduleService

router = APIRouter()
logger = logging.getLogger(__name__)

def get_user_roles_list(user_id: int, db: Session) -> list[str]:
    """Helper para obtener roles del usuario"""
    user_roles = db.exec(
        select(UserRole.role).where(UserRole.user_id == user_id)
    ).all()
    return list(user_roles)

def _build_shift_read(shift: ShiftSchedule) -> ShiftScheduleRead:
    """
    Construir ShiftScheduleRead desde un objeto ShiftSchedule.
    """
    return ShiftScheduleRead(
        id=shift.id,
        user_id=shift.user_id,
        department=shift.department,
        date=shift.date,
        shift_type=shift.shift_type,
        status=shift.status,
        notes=shift.notes,
        created_at=shift.created_at,
        updated_at=shift.updated_at,
        modified_by_user_id=shift.modified_by_user_id,
        user_full_name=shift.user.full_name if shift.user else "Sin asignar",
        user_email=shift.user.email if shift.user else "",
        modified_by_full_name=shift.modified_by.full_name if shift.modified_by else None,
    )


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
    
    logger.info(f"GET shifts: {start_date} → {end_date} | dept={department}")

    # FIX: usamos text() con parámetros explícitos en lugar de comparar
    # ShiftSchedule.status == ShiftStatus.CONFIRMED
    # Esto evita cualquier problema de conversión de enum en SQLModel/SQLAlchemy
    raw_query = text("""
        SELECT ss.*, 
               u.full_name as user_full_name_raw,
               u.email as user_email_raw,
               mu.full_name as modified_by_full_name_raw
        FROM shift_schedules ss
        LEFT JOIN "user" u ON ss.user_id = u.id
        LEFT JOIN "user" mu ON ss.modified_by_user_id = mu.id
        WHERE ss.date >= :start_date
          AND ss.date <= :end_date
          AND ss.department = :department
          AND LOWER(ss.status) = 'confirmed'
        ORDER BY ss.date ASC
    """)

    params = {
        "start_date": start_date,
        "end_date": end_date,
        "department": department,
    }

    if user_id:
        raw_query = text("""
            SELECT ss.*, 
                   u.full_name as user_full_name_raw,
                   u.email as user_email_raw,
                   mu.full_name as modified_by_full_name_raw
            FROM shift_schedules ss
            LEFT JOIN "user" u ON ss.user_id = u.id
            LEFT JOIN "user" mu ON ss.modified_by_user_id = mu.id
            WHERE ss.date >= :start_date
              AND ss.date <= :end_date
              AND ss.department = :department
              AND LOWER(ss.status) = 'confirmed'
              AND ss.user_id = :user_id
            ORDER BY ss.date ASC
        """)
        params["user_id"] = user_id

    rows = db.exec(raw_query, params=params).mappings().all()

    logger.info(f"Turnos encontrados: {len(rows)}")

    result = []
    for row in rows:
        try:
            shift_read = ShiftScheduleRead(
                id=row["id"],
                user_id=row["user_id"],
                department=row["department"],
                date=row["date"],
                shift_type=row["shift_type"],
                status=row["status"],
                notes=row.get("notes"),
                created_at=row["created_at"],
                updated_at=row.get("updated_at"),
                modified_by_user_id=row.get("modified_by_user_id"),
                user_full_name=row.get("user_full_name_raw") or "Sin asignar",
                user_email=row.get("user_email_raw") or "",
                modified_by_full_name=row.get("modified_by_full_name_raw"),
            )
            result.append(shift_read)
        except Exception as e:
            logger.error(f"Error construyendo ShiftScheduleRead para row {row.get('id')}: {e}")
            continue

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
    
    ShiftScheduleService.validate_early_shift_capacity(db, shift_data.date, shift_data.shift_type)
    
    ShiftScheduleService.validate_duplicate_assignment(db, current_user.id, shift_data.date)
    
    # Crear turno
    new_shift = ShiftSchedule(
        **shift_data.model_dump(),
        user_id=current_user.id,
    )
    
    db.add(new_shift)
    db.commit()
    db.refresh(new_shift)
    
    return _build_shift_read(new_shift)


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
    
    return _build_shift_read(shift)


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
            col(ShiftSchedule.status) == "confirmed",
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
