from datetime import datetime, date as date_type, time, timedelta
from typing import Optional
from fastapi import HTTPException
from sqlmodel import Session, select
from app.models.shift_schedule import ShiftSchedule, ShiftType, ShiftStatus
from app.models.user import User
import holidays

# Feriados de Argentina
ar_holidays = holidays.Argentina()

class ShiftScheduleService:
    """Lógica de negocio para gestión de turnos"""
    
    @staticmethod
    def validate_date(target_date: date_type, is_supervisor: bool = False) -> None:
        """Validar que la fecha sea válida para asignación"""
        today = datetime.now().date()
        
        # 1. No asignar en fechas pasadas
        if target_date < today and not is_supervisor:
            raise HTTPException(
                status_code=400,
                detail="No se pueden asignar turnos en fechas pasadas"
            )
        
        # 2. Validar que no sea fin de semana para turno early
        if target_date.weekday() >= 5:  # 5=Sábado, 6=Domingo
            raise HTTPException(
                status_code=400,
                detail="No hay turnos early los fines de semana"
            )
    
    @staticmethod
    def validate_modification_deadline(
        target_date: date_type, 
        current_user_id: int,
        shift_user_id: int,
        user_roles: list[str]
    ) -> None:
        """Validar que se pueda modificar según el deadline"""
        
        is_supervisor = any(role in ["admin", "manager"] for role in user_roles)

        # Supervisores pueden modificar sin restricciones
        if is_supervisor:
            return
        
        # Usuarios solo pueden modificar sus propios turnos
        if current_user_id != shift_user_id:
            raise HTTPException(
                status_code=403,
                detail="No puedes modificar turnos de otros usuarios"
            )
        
        # Validar deadline: día anterior a las 17hs
        now = datetime.now()
        deadline = datetime.combine(
            target_date - timedelta(days=1),
            time(17, 0)  # 17:00 hs
        )
        
        if now > deadline:
            raise HTTPException(
                status_code=400,
                detail=f"No se puede modificar. El plazo límite era {deadline.strftime('%d/%m/%Y a las %H:%M')}"
            )
    
    @staticmethod
    def validate_early_shift_capacity(
        db: Session,
        target_date: date_type,
        shift_type: ShiftType,
        exclude_shift_id: Optional[int] = None
    ) -> None:
        """Validar que no haya más de 1 persona en turno early"""
        
        if shift_type != ShiftType.EARLY:
            return  # No hay límite para turnos regulares
        
        # Buscar turnos early confirmados para esa fecha
        query = select(ShiftSchedule).where(
            ShiftSchedule.date == target_date,
            ShiftSchedule.shift_type == ShiftType.EARLY,
            ShiftSchedule.status == ShiftStatus.CONFIRMED
        )
        
        # Excluir el turno actual si estamos editando
        if exclude_shift_id:
            query = query.where(ShiftSchedule.id != exclude_shift_id)
        
        existing_shift = db.exec(query).first()
        
        if existing_shift:
            raise HTTPException(
                status_code=409,
                detail=f"El turno early ya está ocupado por {existing_shift.user.full_name}"
            )
    
    @staticmethod
    def validate_duplicate_assignment(
        db: Session,
        user_id: int,
        target_date: date_type,
        exclude_shift_id: Optional[int] = None
    ) -> None:
        """Validar que un usuario no tenga 2 turnos el mismo día"""
        
        query = select(ShiftSchedule).where(
            ShiftSchedule.user_id == user_id,
            ShiftSchedule.date == target_date,
            ShiftSchedule.status == ShiftStatus.CONFIRMED
        )
        
        if exclude_shift_id:
            query = query.where(ShiftSchedule.id != exclude_shift_id)
        
        existing = db.exec(query).first()
        
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Ya tienes un turno asignado para ese día"
            )
    
    @staticmethod
    def check_unassigned_alerts(
        db: Session,
        department: str = "stock"
    ) -> list[dict]:
        """
        Verificar turnos sin asignar para alertas
        Retorna lista de alertas para días cercanos sin asignación
        """
        alerts = []
        today = datetime.now().date()
        
        # Revisar próximos 7 días
        for i in range(1, 8):
            check_date = today + timedelta(days=i)
            
            # Saltar fines de semana y feriados
            if check_date.weekday() >= 5 or check_date in ar_holidays:
                continue
            
            # Verificar si hay turno early asignado
            early_shift = db.exec(
                select(ShiftSchedule).where(
                    ShiftSchedule.date == check_date,
                    ShiftSchedule.shift_type == ShiftType.EARLY,
                    ShiftSchedule.status == ShiftStatus.CONFIRMED,
                    ShiftSchedule.department == department
                )
            ).first()
            
            if not early_shift and i <= 2:  # Alertar solo para próximos 2 días
                alerts.append({
                    "date": check_date,
                    "shift_type": "early",
                    "days_until": i,
                    "severity": "high" if i == 1 else "medium"
                })
        
        return alerts