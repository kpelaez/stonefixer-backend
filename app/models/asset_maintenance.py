from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from .tech_asset import TechAsset
    from .user import User


class MaintenanceType(str, Enum):
    """Tipos de mantenimiento"""
    PREVENTIVE = "preventive"
    CORRECTIVE = "corrective"
    UPGRADE = "upgrade"
    CLEANING = "cleaning"
    CALIBRATION = "calibration"
    REPAIR = "repair"
    REPLACEMENT = "replacement"
    INSPECTION = "inspection"


class MaintenanceStatus(str, Enum):
    """Estados del mantenimiento"""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELED = "canceled"
    POSTPONED = "postponed"
    PENDING_PARTS = "pending_parts"


class MaintenancePriority(str, Enum):
    """Prioridades de mantenimiento"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AssetMaintenanceBase(SQLModel):
    """Modelo base para mantenimientos de activos"""
    tech_asset_id: int = Field(foreign_key="tech_asset.id", description="ID del activo tecnológico")
    maintenance_type: MaintenanceType = Field(description="Tipo de mantenimiento")
    title: str = Field(description="Título del mantenimiento")
    description: str = Field(description="Descripción detallada del mantenimiento")
    priority: MaintenancePriority = Field(default=MaintenancePriority.MEDIUM, description="Prioridad del mantenimiento")
    status: MaintenanceStatus = Field(default=MaintenanceStatus.SCHEDULED, description="Estado del mantenimiento")

    # Fechas
    scheduled_date: datetime = Field(description="Fecha programada para el mantenimiento")
    estimated_duration_hours: Optional[float] = Field(default=None, ge=0, description="Duración estimada en horas")
    started_at: Optional[datetime] = Field(default=None, description="Fecha y hora de inicio real")
    completed_at: Optional[datetime] = Field(default=None, description="Fecha y hora de finalización")

    # Personal responsable
    requested_by_user_id: Optional[int] = Field(default=None, foreign_key="user.id", description="Usuario que solicitó el mantenimiento")

    # Información técnica
    procedures_performed: Optional[str] = Field(default=None, description="Procedimientos realizados")
    parts_replaced: Optional[str] = Field(default=None, description="Partes reemplazadas")
    tools_used: Optional[str] = Field(default=None, description="Herramientas utilizadas")

    # Costos
    labor_cost: Optional[float] = Field(default=None, ge=0, description="Costo de mano de obra")
    parts_cost: Optional[float] = Field(default=None, ge=0, description="Costo de repuestos")
    external_service_cost: Optional[float] = Field(default=None, ge=0, description="Costo de servicios externos")

    # Información adicional
    maintenance_provider: Optional[str] = Field(default=None, description="Proveedor de mantenimiento")
    warranty_work: bool = Field(default=False, description="¿Es trabajo bajo garantía?")
    follow_up_required: bool = Field(default=False, description="¿Requiere seguimiento?")
    follow_up_date: Optional[datetime] = Field(default=None, description="Fecha de seguimiento")

    # Documentación
    notes: Optional[str] = Field(default=None, description="Notas adicionales")
    attachments: Optional[str] = Field(default=None, description="Rutas de archivos adjuntos")


class AssetMaintenance(AssetMaintenanceBase, table=True):
    """Modelo de tabla para mantenimientos de activos"""
    __tablename__ = "asset_maintenances"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Fecha de creación del registro"
    )
    updated_at: Optional[datetime] = Field(default=None, description="Fecha de última actualización")

    # Relaciones
    tech_asset: Optional["TechAsset"] = Relationship(back_populates="maintenances")
    requested_by_user: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[AssetMaintenance.requested_by_user_id]",
            "primaryjoin": "AssetMaintenance.requested_by_user_id == User.id",
            "lazy": "select",
        }
    )


class AssetMaintenanceRead(AssetMaintenanceBase):
    """Esquema de lectura para mantenimientos"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class AssetMaintenanceCreate(SQLModel):
    """Esquema de creación para mantenimientos"""
    tech_asset_id: int
    maintenance_type: MaintenanceType
    title: str
    description: str
    priority: MaintenancePriority = MaintenancePriority.MEDIUM
    scheduled_date: datetime
    estimated_duration_hours: Optional[float] = None
    requested_by_user_id: Optional[int] = None
    maintenance_provider: Optional[str] = None
    warranty_work: bool = False
    notes: Optional[str] = None


class AssetMaintenanceUpdate(SQLModel):
    """Esquema de actualización para mantenimientos"""
    maintenance_type: Optional[MaintenanceType] = None
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[MaintenancePriority] = None
    status: Optional[MaintenanceStatus] = None
    scheduled_date: Optional[datetime] = None
    estimated_duration_hours: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    procedures_performed: Optional[str] = None
    parts_replaced: Optional[str] = None
    tools_used: Optional[str] = None
    labor_cost: Optional[float] = None
    parts_cost: Optional[float] = None
    external_service_cost: Optional[float] = None
    maintenance_provider: Optional[str] = None
    warranty_work: Optional[bool] = None
    follow_up_required: Optional[bool] = None
    follow_up_date: Optional[datetime] = None
    notes: Optional[str] = None


class StartMaintenance(SQLModel):
    """Esquema para iniciar mantenimiento"""
    started_at: Optional[datetime] = None
    notes: Optional[str] = None


class CompleteMaintenance(SQLModel):
    """Esquema para completar un mantenimiento"""
    completed_at: Optional[datetime] = None
    procedures_performed: Optional[str] = None
    parts_replaced: Optional[str] = None
    tools_used: Optional[str] = None
    labor_cost: Optional[float] = None
    parts_cost: Optional[float] = None
    external_service_cost: Optional[float] = None
    follow_up_required: bool = False
    follow_up_date: Optional[datetime] = None
    notes: Optional[str] = None


class AssetMaintenanceWithDetails(AssetMaintenanceRead):
    """Mantenimiento con detalles del activo y personal"""
    tech_asset_name: Optional[str] = None
    tech_asset_serial: Optional[str] = None
    tech_asset_brand: Optional[str] = None
    tech_asset_model: Optional[str] = None
    technician_name: Optional[str] = None
    requested_by_name: Optional[str] = None
    total_cost: Optional[float] = None


class MaintenanceSchedule(SQLModel):
    """Resumen para calendario de mantenimientos"""
    id: int
    title: str
    tech_asset_name: str
    scheduled_date: datetime
    estimated_duration_hours: Optional[float] = None
    priority: MaintenancePriority
    status: MaintenanceStatus
    technician_name: Optional[str] = None


class MaintenanceMetrics(SQLModel):
    """Métricas de mantenimiento"""
    total_maintenances: int
    completed_maintenances: int
    pending_maintenances: int
    overdue_maintenances: int
    average_completion_time_hours: Optional[float] = None
    total_maintenance_cost: Optional[float] = None
    preventive_vs_corrective_ratio: Optional[float] = None