from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, TYPE_CHECKING
from sqlmodel import Column, SQLModel, Field, Relationship, String

if TYPE_CHECKING:
    from .tech_asset import TechAsset
    from .user import User

class AssignmentStatus(str, Enum):
    """Estados de las asignaciones de activos"""
    ACTIVE = "active"           #Asignacion activa
    RETURNED = "returned"       #Activo devuelto
    TRANSFERED = "transfered"   #Transferido a otro usuario
    LOST = "lost"               #Activo perdido
    DAMAGED = "damaged"         #Activo dañado durante asignacion
    CANCELED = "canceled"       #La asignacion fue cancelada

class AssetAssignmentBase(SQLModel):
    """Modelo base para asignaciones de activos"""
    tech_asset_id: Optional[int] = Field(foreign_key="tech_asset.id", description="ID del activo tecnologico")
    assigned_to_user_id: int = Field(foreign_key="user.id", description="ID del usuario asignado")
    requested_by_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    assigned_date: datetime = Field(default_factory= lambda: datetime.now(timezone.utc), description="Fecha de asignación")
    expected_return_date: Optional[datetime] = Field(default=None, description="Fecha esperada de devoluciones")
    actual_return_date: Optional[datetime] = Field(default=None, description="Fecha real de devolución")
    status: AssignmentStatus = Field(default=AssignmentStatus.ACTIVE, sa_column=Column(String, nullable=False, default="active"), description="Estado de la asignación")
    accessories: Optional[str] = Field(default=None, description="Accesorios entregados con el activo")

    # Informacion adicional
    assignment_reason: Optional[str] = Field(default=None, description="Motivo de la asignación")
    location_of_use: Optional[str] = Field(default=None, description="Ubicación donde se usara el activo")
    assigned_by_user_id: Optional[int] = Field(default=None, foreign_key="user.id", description="Usuario que realizo la asignación")

    # Condicion del activo
    condition_at_assignment: Optional[str] = Field(default=None, description="Condición del activo al momento de asignación")
    condition_at_return: Optional[str] = Field(default=None, description="Condición del activo al momento de devolución")

    # Notas
    assignment_notes: Optional[str] = Field(default=None, description="Notas sobre la asignación")
    return_notes: Optional[str] = Field(default=None, description="Notas sobre la devolución")

class AssetAssignment(AssetAssignmentBase, table=True):
    """Modelo de tabla para asignaciones de activos"""
    __tablename__ = "asset_assignments"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda:datetime.now(timezone.utc), description="Fecha de creacion del registro")
    updated_at: Optional[datetime] = Field(default=None, description="Fecha de ultima actualizacion")

    # Integracion con Humand
    humand_document_name: Optional[str] = Field(default=None, description="Nombre del documento en Humand")
    document_sent_to_humand: bool = Field(default=False, description="Si el documento fue enviado a Humand")
    document_sent_at: Optional[datetime] = Field(default=None, description="Fecha de envio a Humand")
    humand_folder_id: Optional[int] = Field(default=None, description="ID de carpeta en Humand")
    
    # Relaciones
    tech_asset: Optional["TechAsset"] = Relationship(back_populates="assignments")
    assigned_to_user: Optional["User"] = Relationship(sa_relationship_kwargs={
        "foreign_keys": "[AssetAssignment.assigned_to_user_id]",
        "primaryjoin": "AssetAssignment.assigned_to_user_id == User.id",
        "lazy": "select",
    })
    assigned_by_user: Optional["User"] = Relationship(sa_relationship_kwargs={
        "foreign_keys": "[AssetAssignment.assigned_by_user_id]",
        "primaryjoin": "AssetAssignment.assigned_by_user_id == User.id",
        "lazy": "select",
    })
    
class AssetAssignmentRead(AssetAssignmentBase):
    """Esquema de lectura para asignaciones"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

class AssetAssignmentCreate(SQLModel):
    """Esquema de creación para asignaciones"""
    tech_asset_id: int
    assigned_to_user_id: int
    expected_return_date: Optional[str] = None
    assignment_reason: Optional[str] = None
    location_of_use: Optional[str] = None
    condition_at_assignment: Optional[str] = None
    assignment_notes: Optional[str] = None

class AssetAssignmentUpdate(SQLModel):
    """Esquema de actualización para asignaciones"""
    expected_return_date: Optional[datetime] = None
    actual_return_date: Optional[datetime] = None
    status: Optional[AssignmentStatus] = None
    assignment_reason: Optional[str] = None
    location_of_use: Optional[str] = None
    condition_at_assignment: Optional[str] = None
    condition_at_return: Optional[str] = None
    assignment_notes: Optional[str] = None
    return_notes: Optional[str] = None

class AssetReturn(SQLModel):
    """Esquema para marcar un activo como devuelto"""
    actual_return_date: Optional[datetime] = None
    condition_at_return: Optional[str] = None
    return_notes: Optional[str] = None
    status: AssignmentStatus = AssignmentStatus.RETURNED

# Esquemas extendidos con información relacionada
class AssetAssignmentWithDetails(AssetAssignmentRead):
    """Asignación con detalles del activo y usuario"""
    tech_asset_name: Optional[str] = None
    tech_asset_serial: Optional[str] = None
    tech_asset_brand: Optional[str] = None
    tech_asset_model: Optional[str] = None
    tech_asset_asset_tag: Optional[str] = None
    assigned_to_name: Optional[str] = None
    assigned_to_email: Optional[str] = None
    assigned_by_name: Optional[str] = None
    # Campos de informacion Humand
    document_sent_to_humand: bool = False
    document_sent_at: Optional[datetime] = None
    humand_document_name: Optional[str] = None
    humand_folder_id: Optional[int] = None

class UserAssignmentSummary(SQLModel):
    """Resumen de asignaciones por usuario"""
    user_id: int
    user_name: str
    user_email: str
    active_assignments: int
    total_assignments: int
    assets_in_possession: List[str] = []

