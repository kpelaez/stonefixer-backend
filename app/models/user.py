from pydantic import field_validator
from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime, timezone


if TYPE_CHECKING:
    from .role import UserRole

class UserBase(SQLModel):
    email: str = Field(index=True, unique=True)
    full_name: Optional[str] = None
    is_active: bool = True

class User(UserBase, table=True):
    __tablename__ = "user"

    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str

    # Registro auditable de la última vez que el usuario cambió su propia
    # contraseña (no se usa para bloquear login, solo para trazabilidad)
    password_changed_at: Optional[datetime] = Field(default=None)

    dni_encrypted: Optional[str] = Field(default=None, description="DNI encriptado con Fernet")
    dni_hash: Optional[str] = Field(default=None, index=True, description="Hash SHA256 del DNI para busquedas")

    # Consentimiento
    personal_data_consent: bool = Field(default=False, description="Consentimientos uso de datos")
    personal_data_consent_date: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relacion con roles
    roles: List['UserRole'] = Relationship(back_populates="user")

class UserCreate(UserBase):
    password: str
    roles: List[str] = []

class UserRead(UserBase):
    id: int
    created_at: datetime
    roles: List[str] = []

class UserLogin(SQLModel):
    email: str
    password: str

class UserDNIUpdate(SQLModel):
    """Schema para actualizar el DNI de un usuario"""
    dni: str
    consent: bool = False



# NUEVO: self-service, requiere password actual
class PasswordChange(SQLModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        from app.core.password_policy import validate_password_strength
        return validate_password_strength(v)
    
# NUEVO: reset por admin, sin conocer el password actual — marca must_change_password
class AdminPasswordReset(SQLModel):
    new_password: str

