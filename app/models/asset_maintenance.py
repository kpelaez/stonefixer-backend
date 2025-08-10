from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship

# Forward references para las relaciones
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .tech_asset import TechAsset
    from .user import User

class MaintenanceType(str, Enum):
    """Tipos de mantenimiento"""
    PREVENTIVE = "preventive"
    CORRECTIVE = "corective"
    UPGRADE = "upgrade"
    CLEANING = "cleaning"
    CALIBRATION = "calibration"
    REPAIR = "repair"
    REPLACEMENT = "replacement"
    INSPECTION = "Inspection"
    
class MaintenanceStatus(str, Enum):
    """Estados del mantenimiento"""
    SCHEDULED = "scheduled"         #Programado
    IN_PROGRESS = "in_progress"     #En progreso
    COMPLETED = "completed"         #Completado
    CANCELLED = "cancelled"         #Cancelado
    POSTPONED = "postponed"         #Pospuesto
    PENDING_PARTS = "pending_parts" #Esperando repuestos

class MaintenancePriority(str, Enum):
    """Prioridades de mantenimiento"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AssetMaintenanceBase(SQLModel):
    """Modelo base para mantenimientos de activos"""
    tech_asset_id: int = Field(foreign_key="tech_asset.id", description="ID del activo tecnologico")
    maintenance_type: MaintenanceType = Field(description="Tipo de mantenimiento")
    title: str = Field(description="Titulo del mantenimiento")
    description: str = Field(description="Descripcion detallada del mantenimiento")
    priority: MaintenancePriority = Field(default=MaintenancePriority.MEDIUM, description="Prioridad del mantenimiento")
    status: MaintenanceStatus = Field(default=MaintenanceStatus.SCHEDULED, description="Estado del mantenimiento")

    # Fechas
    scheduled_date: datetime = Field(description="Fecha programada para el mantenimiento")
    estimated_duration_hours: Optional[float] = Field(default=None, ge=0, description="Duracion estimada en horas")
    started_at: Optional[datetime] = Field(default=None, description="Fehca y hora de inicio real")
    completed_at: Optional[datetime] = Field(default=None, description="Fecha y hora de finalizacion")

    # Personal responsable
    requested_by_user_id : Optional[int] = Field(default=None, foreign_key="user.id", description="Usuario que solicito el mantenimiento")

    # Informacion tecnica
    procedures_performed: Optional[str] = Field(default=None, description="Procedimientos realizados")
    parts_replaced: Optional[str] = Field(default=None, description="Partes reemplazadas")
    tools_used: Optional[str] = Field(default=None, description="Herramientas utilizadas")

    # Costos
    labor_cost: Optional[float] = Field(default=None, ge=0, description="Costo de mano de obra")
    parts_cost: Optional[float] = Field(default=None, ge=0, description="Costo de repuestos")
    external_service_cost: Optional[float] = Field(default=None, ge=0, description="Costo de servicios externos")

    # Informacion adicional
    maintenance_provider: Optional[str] = Field(default=None, description="Proveedor de mantenimiento")
    warranty_work: bool = Field(default=False, description="¿Es trabajo bajo garantia?")
    follow_up_required: bool = Field(default=False, description="¿Requiere seguimiento?")
    follow_up_date: Optional[datetime] = Field(default=None, description="Fecha de seguimiento")

    # Documentacion
    notes: Optional[str] = Field(default=None, description="Notas adicionales")
    attachments: Optional[str] = Field(default=None, description="Rutas de archivos adjuntos")

class AssetMaintenance(AssetMaintenanceBase, table=True):
    """Modelo de tabla para mantenimientos de activos"""
    __tablename__ = "asset_maintenances"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Fecha de creacion del registro")
    updated_at: Optional[datetime] = Field(default=None, description="Fecha de ultima actualizacion")

    # Relaciones
    tech_asset: 'TechAsset' = Relationship(back_populates="maintenances")
    requested_by_user: Optional['User'] = Relationship()

class AssetMaintenanceRead(AssetMaintenanceBase):
    """Esquema de lectura para mantenimientos"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

class AssetMaintenanceCreate(SQLModel):
    """Esquema de creacion para mantenimientos"""
    tech_asset_id: int
    maintenance_type: MaintenanceType
    title: str
    description: str
    priority: MaintenancePriority = MaintenancePriority.MEDIUM
    scheduled_date: datetime
    estimated_duration_hours: Optional[float] = None
    assigned_technician_id: Optional[int] = None
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
    assigned_technician_id: Optional[int] = None
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
    """"Esquema para iniciar mantenimiento"""
    started_at: Optional[datetime] = None
    notes: Optional[str] = None

class CompleteMaintenance(SQLModel):
    """Esquema para compeltar un mantenimiento"""
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

# Esquemas extendidos con información relacionada
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


