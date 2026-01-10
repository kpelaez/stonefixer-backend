from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime, date as date_type, timezone
from enum import Enum

if TYPE_CHECKING:
    from .user import User

class ShiftType(str, Enum):
    """Tipos de turno disponibles"""
    EARLY = "early" #7:00 AM
    REGULAR = "regular" #9:00 AM

class ShiftStatus(str, Enum):
    """Estados posibles de un turno"""
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"

class ShiftScheduleBase(SQLModel):
    """Base model para turnos"""

    user_id: int = Field(foreign_key="user.id", description="Usuario asignado al turno")
    department: str = Field(default="stock", index=True, description="Departamento")
    date: date_type = Field(index=True, description="Fecha del turno")
    shift_type: ShiftType = Field(description="Tipo de turno")
    status: ShiftStatus = Field(default=ShiftStatus.CONFIRMED, description="Estado del turno") 
    notes: Optional[str] = Field(default=None, max_length=500, description="Notas opcionales del turno")

    # Auditoria
    modified_by_user_id: Optional[int] = Field(default=None, foreign_key="user.id", description="ID del usuario que modifico el turno")



class ShiftSchedule(ShiftScheduleBase, table= True):
    """Modelo de tabla para programacion de turnos"""
    __tablename__ = "shift_schedules"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Fecha de creacion")
    updated_at: Optional[datetime] = Field(default=None, description="Fecha de ultima actualziacion")

    # Relaciones
    user: 'User' = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[ShiftSchedule.user_id]",
            "primaryjoin": "ShiftSchedule.user_id == User.id"
        })

    modified_by: Optional['User'] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[ShiftSchedule.modified_by_user_id]",
            "primaryjoin": "ShiftSchedule.modified_by_user_id == User.id"
        }
    )

# === SCHEMAS PARA API ===

class ShiftScheduleCreate(SQLModel):
    """Schema para crear un nuevo turno"""
    date: date_type
    shift_type: ShiftType
    notes: Optional[str] = None

class ShiftScheduleUpdate(SQLModel):
    """Schema para actualizar un turno existente"""
    date: Optional[date_type] = None
    shift_type: Optional[ShiftType] = None
    status: Optional[ShiftStatus] = None
    notes: Optional[str] = None

class ShiftScheduleRead(ShiftScheduleBase):
    """Schema de lectura con información del usuario"""
    id: int
    user_id: int
    department: str
    date: date_type
    shift_type: ShiftType
    status: ShiftStatus
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Información extendida del usuario
    user_full_name: Optional[str] = None
    user_email: Optional[str] = None
    
    # Información de quien modificó (si aplica)
    modified_by_user_id: Optional[int] = None
    modified_by_full_name: Optional[str] = None

class ShiftScheduleStats(SQLModel):
    """Estadísticas de turnos por usuario"""
    user_id: int
    user_full_name: str
    total_shifts: int
    early_shifts: int
    regular_shifts: int
    percentage_of_total: float  # % del total de turnos del equipo
    
class ShiftScheduleAlert(SQLModel):
    """Alertas de turnos sin asignar"""
    date: date_type
    shift_type: ShiftType
    days_until: int  # Días hasta la fecha
    message: str