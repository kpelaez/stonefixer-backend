from enum import Enum
from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, timezone

#TechAssetResponse, TechAssetUpdate, TechAssetCreate

class AssetStatus(str, Enum):
    """Estados posibles de un activo tecnologico"""
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    IN_MAINTENANCE = "in_maintenance"
    OUT_OF_ORDER = "out_of_order"
    RETIRED = "retired"


class AssetCategory(str, Enum):
    """Categorias de activos tecnologicos"""
    NOTEBOOK = "Notebook"
    DESKTOP = "desktop"
    MONITOR = "Monitor"
    TECLADO = "Teclado"
    MOUSE = "mouse"
    KIT_TECLADO_MOUSE = "kit_teclado_mouse"
    IMPRESORA = "impresora"
    TABLET = "tablet"
    CELULAR = "celular"
    SERVER = "servidor"
    ROUTER = "router"
    ACCESORIOS = "accesorios"
    SOFTWARE = "software"
    CABLE = "cable"
    OTRO = "otro"

class TechAssetBase(SQLModel):
    """Modelo base para activos tecnologicos"""
    name: str = Field(index= True, description="Nombre del activo")
    description: Optional[str] = Field(default=None, description="Descripcion detallada")
    brand: str = Field(description="Marca del activo")
    model: str = Field(description="Modelo del activo")
    serial_number: str = Field(unique = True, description="Numero de serie unico")
    asset_tag: Optional[str] = Field(default=None, unique=True, index=True, description="Etiqueta de activo de la empresa")
    category: AssetCategory = Field(description="Categoria del activo")
    status: AssetStatus = Field(default=AssetStatus.AVAILABLE, description="Estado actual del activo")

    # Informacion financiera
    purchase_price: Optional[float] = Field(default=None, ge=0, description="Precio de compra")
    purchase_date: Optional[datetime] = Field(default=None, description="Fecha de compra del activo")
    supplier: Optional[str] = Field(default=None, description="Proveedor")

    # Informacion de garantia
    warranty_expiry: Optional[datetime] = Field(default=None, description="Fecha de vencimiento de garantia")
    
    # Ubicacion y departamento
    location: Optional[str] = Field(default=None, description="Ubicacion del activo")
    department: Optional[str] = Field(default=None, description="Departamento responsable")
    user_assigned: Optional[str] = Field(default=None, description="Usuario designado del activo tecnologico")

    # Especificaciones tecnicas 
    specifications: Optional[str] = Field(default=None, description="Especificaciones tecnicas")

    # Notas adicionales
    notes: Optional[str] = Field(default=None, description="Notas adicionales")

class TechAsset(TechAssetBase, table= True):
    """Modelo de tabla para activos tecnologicos"""
    __tablename__ = "tech_assets"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now(timezone.utc), description="Fecha de creacion del registro")
    updated_at: Optional[datetime] = Field(default=None, description="Fecha de ultima actualizacion")

    # Relaciones
    assignments: List["AssetAssignment"] = Relationship(back_populates="tech_asset")
    maintenances: List["AssetMaintenance"] = Relationship(back_populates="tech_asset")

class TechAssetResponse(TechAssetBase):
    """Esquema de lectura para activos tecnologicos"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

class TechAssetCreate(TechAssetBase):
    """Esquema de creacion para activos tecnologicos"""
    pass

class TechAssetUpdate(SQLModel):
    """Esquema de actualizacion para activos tecnologicos"""
    name: Optional[str] = None
    description: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    asset_tag: Optional[str] = None
    category: Optional[AssetCategory] = None
    status: Optional[AssetStatus] = None

    # Informacion financiera
    purchase_price: Optional[float] = None
    purchase_date: Optional[datetime] = None
    supplier: Optional[str] = None

    # Informacion de garantia
    warranty_expiry: Optional[datetime] = None
    
    # Ubicacion y departamento
    location: Optional[str] = None
    department: Optional[str] = None
    user_assigned: Optional[str] = None

    # Especificaciones tecnicas
    specifications: Optional[str] = None

    # Notas adicionales
    notes: Optional[str] = None

class TechAssetSummary(SQLModel):
    """Resumen de activo para listados"""
    id: int
    name: str
    brand: str
    model: str
    serial_number: str
    asset_tag: Optional[str] = None
    category: AssetCategory
    status: AssetStatus
    location: Optional[str] = None
    department: Optional[str] = None
    user_assigned: Optional[str] = None

class TechAssetWithAssignment(TechAssetResponse):
    """Activo con información de asignación actual"""
    current_assignment: Optional["AssetAssignmentRead"] = None
    assigned_to: Optional[str] = None  # Nombre del usuario asignado

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .asset_assignment import AssetAssignment, AssetAssignmentRead
    from .asset_maintenance import AssetMaintenance