from decimal import Decimal
from enum import Enum
from typing import Optional, TYPE_CHECKING
from sqlmodel import Column, Field, Numeric, Relationship, SQLModel, String
from datetime import date, datetime, timezone

if TYPE_CHECKING:
    from .user import User


class OvertimeType(str, Enum):
    """
    CREDIT: El empleado trabajó horas extra → su saldo sube.
    DEBIT:  El empleado toma tiempo compensatorio → su saldo baja.
    """
    CREDIT = "credit"
    DEBIT = "debit"


class OvertimeStatus(str, Enum):
    PENDING = "pending"       # Solicitado, esperando aprobación
    APPROVED = "approved"     # Aprobado → afecta al saldo
    REJECTED = "rejected"     # Rechazado → sin efecto en saldo
    CANCELLED = "cancelled"   # Cancelado por el propio empleado (solo si PENDING)



class OvertimeEntryBase(SQLModel):
    user_id: int = Field(foreign_key="user.id", index=True)
    entry_type: OvertimeType = Field(
        sa_column=Column(String, nullable=False),
        description="CREDIT = trabajó extra | DEBIT = toma compensatorio"
    )
    hours: Decimal = Field(
        sa_column=Column(Numeric(precision=5, scale=2), nullable=False),
        description="Horas (ej: 1.5 = 1h 30min). Siempre positivo.",
        gt=0,
        le=24,
    )
    reference_date: date = Field(
        index=True,
        description="Fecha en que se trabajaron las HE o se tomará el compensatorio"
    )
    reason: str = Field(
        max_length=500,
        description="Motivo obligatorio. Ej: 'Cierre de inventario mensual'"
    )


class OvertimeEntry(OvertimeEntryBase, table=True):
    __tablename__ = "overtime_entries"

    id: Optional[int] = Field(default=None, primary_key=True)

    status: OvertimeStatus = Field(
        default=OvertimeStatus.PENDING,
        sa_column=Column(String, nullable=False, default="pending"),
    )

    # Auditoría
    requested_by_user_id: int = Field(
        foreign_key="user.id",
        description="Quién creó la solicitud (puede ser el mismo empleado o un manager)"
    )
    reviewed_by_user_id: Optional[int] = Field(
        default=None,
        foreign_key="user.id",
        description="Manager que aprobó o rechazó"
    )
    review_note: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Comentario del manager al aprobar/rechazar"
    )
    reviewed_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: Optional[datetime] = Field(default=None)

    # Relaciones
    user: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[OvertimeEntry.user_id]",
            "primaryjoin": "OvertimeEntry.user_id == User.id",
            "lazy": "select",
        }
    )
    requested_by: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[OvertimeEntry.requested_by_user_id]",
            "primaryjoin": "OvertimeEntry.requested_by_user_id == User.id",
            "lazy": "select",
        }
    )
    reviewed_by: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[OvertimeEntry.reviewed_by_user_id]",
            "primaryjoin": "OvertimeEntry.reviewed_by_user_id == User.id",
            "lazy": "select",
        }
    )



class OvertimeEntryCreate(SQLModel):
    """El empleado crea una solicitud."""
    user_id: int
    entry_type: OvertimeType
    hours: Decimal
    reference_date: date
    reason: str


class OvertimeEntryReview(SQLModel):
    """El manager aprueba o rechaza. Solo cambia status y review_note."""
    status: OvertimeStatus  # Solo APPROVED o REJECTED válidos aquí
    review_note: Optional[str] = None


class OvertimeEntryRead(SQLModel):
    id: int
    user_id: int
    user_full_name: str
    entry_type: OvertimeType
    hours: Decimal
    reference_date: date
    reason: str
    status: OvertimeStatus
    review_note: Optional[str]
    reviewed_at: Optional[datetime]
    reviewed_by_full_name: Optional[str]
    created_at: datetime


class OvertimeBalanceRead(SQLModel):
    """Saldo calculado dinamicamente. Nunca se persiste."""
    user_id: int
    user_full_name: str
    total_credit_hours: Decimal    # HE aprobadas acumuladas
    total_debit_hours: Decimal     # Compensatorios aprobados tomados
    balance_hours: Decimal         # credit - debit
    pending_credit_hours: Decimal  # Solicitudes aún no revisadas
    pending_debit_hours: Decimal