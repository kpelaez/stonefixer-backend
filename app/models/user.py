from sqlmodel import SQLModel, Field, Relationship
from typing import List
from datetime import datetime, timezone
from app.models.role import UserRole

class UserBase(SQLModel):
    email: str = Field(index=True, unique=True)
    full_name: str | None = None
    is_active: bool = True

class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relacion con roles
    roles: List["UserRole"] = Relationship(back_populates="user")

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