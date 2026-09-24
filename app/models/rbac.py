from typing import List, Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum

if TYPE_CHECKING:
    pass


class PermissionAction(str, Enum):
    """Acciones posibles sobre un módulo. No todos los módulos usan todas."""
    VIEW = "view"
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    APPROVE = "approve"


class RoleDB(SQLModel, table=True):
    """Roles configurables del sistema (reemplaza gradualmente al enum Role)."""
    __tablename__ = "roles"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, description="Ej: 'Analista', 'Jefe', 'Gerente'")
    hierarchy_level: int = Field(description="Solo para orden/UI, NO otorga permisos por sí mismo")
    description: Optional[str] = None

    permissions: List["RolePermission"] = Relationship(back_populates="role")


class Module(SQLModel, table=True):
    """Módulos funcionales de la plataforma."""
    __tablename__ = "modules"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True, description="Ej: 'inventario', 'horas_extra'")
    name: str = Field(description="Nombre mostrado en UI")

    permissions: List["Permission"] = Relationship(back_populates="module")


class Permission(SQLModel, table=True):
    """Combinación módulo + acción. Ej: horas_extra:approve"""
    __tablename__ = "permissions"

    id: Optional[int] = Field(default=None, primary_key=True)
    module_id: int = Field(foreign_key="modules.id")
    action: str = Field(description="view | create | edit | delete | approve")

    module: Module = Relationship(back_populates="permissions")
    role_links: List["RolePermission"] = Relationship(back_populates="permission")


class RolePermission(SQLModel, table=True):
    """La matriz configurable: qué permisos tiene cada rol."""
    __tablename__ = "role_permissions"

    role_id: int = Field(foreign_key="roles.id", primary_key=True)
    permission_id: int = Field(foreign_key="permissions.id", primary_key=True)

    role: RoleDB = Relationship(back_populates="permissions")
    permission: Permission = Relationship(back_populates="role_links")