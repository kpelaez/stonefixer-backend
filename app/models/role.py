from enum import Enum
from typing import TYPE_CHECKING, Optional
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from .user import User


class Role(str, Enum):
    """Roles disponibles en el sistema"""
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    INVENTORY_MANAGER = "inventory_manager"


class UserRole(SQLModel, table=True):
    """Tabla de relación entre usuarios y roles"""
    __tablename__ = "user_roles"

    user_id: int = Field(foreign_key="user.id", primary_key=True)
    role: str = Field(primary_key=True)

    # NUEVO: FK real hacia la tabla roles nueva,
    # nullable y sin tocar `role` (string legacy). Convive con el
    # sistema viejo hasta que migremos los datos reales.
    role_id: Optional[int] = Field(default=None, foreign_key="roles.id")

    # Relación hacia User
    user: Optional["User"] = Relationship(back_populates="roles")