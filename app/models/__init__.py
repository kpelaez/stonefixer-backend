from .user import User, UserBase, UserCreate, UserRead, UserLogin, UserDNIUpdate
from .role import Role, UserRole
from .tech_asset import (
    TechAsset,
    TechAssetBase,
    TechAssetCreate,
    TechAssetUpdate,
    TechAssetResponse,
    TechAssetSummary,
    TechAssetWithAssignment,
    GenerateAssetTagRequest,
    AssetStatus,
    AssetCategory,
)
from .asset_assignment import (
    AssetAssignment,
    AssetAssignmentBase,
    AssetAssignmentCreate,
    AssetAssignmentUpdate,
    AssetAssignmentRead,
    AssetAssignmentWithDetails,
    AssetReturn,
    UserAssignmentSummary,
    AssignmentStatus,
)
from .asset_maintenance import (
    AssetMaintenance,
    AssetMaintenanceBase,
    AssetMaintenanceCreate,
    AssetMaintenanceUpdate,
    AssetMaintenanceRead,
    AssetMaintenanceWithDetails,
    StartMaintenance,
    CompleteMaintenance,
    MaintenanceSchedule,
    MaintenanceMetrics,
    MaintenanceType,
    MaintenanceStatus,
    MaintenancePriority,
)
from .shift_schedule import (
    ShiftSchedule,
    ShiftScheduleBase,
    ShiftScheduleCreate,
    ShiftScheduleUpdate,
    ShiftScheduleRead,
    ShiftScheduleStats,
    ShiftScheduleAlert,
    ShiftType,
    ShiftStatus,
)

__all__ = [
    # User
    "User", "UserBase", "UserCreate", "UserRead", "UserLogin", "UserDNIUpdate",
    # Role
    "Role", "UserRole",
    # TechAsset
    "TechAsset", "TechAssetBase", "TechAssetCreate", "TechAssetUpdate",
    "TechAssetResponse", "TechAssetSummary", "TechAssetWithAssignment",
    "GenerateAssetTagRequest", "AssetStatus", "AssetCategory",
    # AssetAssignment
    "AssetAssignment", "AssetAssignmentBase", "AssetAssignmentCreate",
    "AssetAssignmentUpdate", "AssetAssignmentRead", "AssetAssignmentWithDetails",
    "AssetReturn", "UserAssignmentSummary", "AssignmentStatus",
    # AssetMaintenance
    "AssetMaintenance", "AssetMaintenanceBase", "AssetMaintenanceCreate",
    "AssetMaintenanceUpdate", "AssetMaintenanceRead", "AssetMaintenanceWithDetails",
    "StartMaintenance", "CompleteMaintenance", "MaintenanceSchedule",
    "MaintenanceMetrics", "MaintenanceType", "MaintenanceStatus", "MaintenancePriority",
    # ShiftSchedule
    "ShiftSchedule", "ShiftScheduleBase", "ShiftScheduleCreate", "ShiftScheduleUpdate",
    "ShiftScheduleRead", "ShiftScheduleStats", "ShiftScheduleAlert",
    "ShiftType", "ShiftStatus",
]