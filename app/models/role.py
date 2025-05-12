from sqlmodel import SQLModel, Field, Relationship
from typing import TYPE_CHECKING
from enum import Enum, auto

class Role(str, Enum):
    ADMIN =  "admin"
    MANAGER = "manager"
    USER = "user"
    VIEWER = "viewer"

# Evitar importación circular
if TYPE_CHECKING:
    from app.models.user import User

class UserRole(SQLModel, table=True):
    """Tabla de relacion entre usuarios y roles"""
    __tablename__ = "user_roles"

    user_id: int = Field(foreign_key="user.id", primary_key=True)
    role: str = Field(primary_key=True)

    user: "User" = Relationship(back_populates="roles")