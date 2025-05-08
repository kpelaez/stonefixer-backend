from sqlmodel import SQLModel, Field
from enum import Enum, auto

class Role(str, Enum):
    ADMIN =  "admin"
    MANAGER = "manager"
    USER = "user"
    VIEWER = "viewer"


class UserRole(SQLModel, talbe=True):
    """Tabla de relacion entre usuarios y roles"""
    __tablename__ = "user_roles"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    role: str = Field(primary_key=True)