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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relacion con roles
    roles: List['UserRole'] = Relationship(back_populates="user")

class UserCreate(UserBase):
    password: str
    roles: List[str] = Field(default_factory=list)

class UserRead(UserBase):
    id: int
    created_at: datetime
    roles: List[str] = Field(default_factory=list)

class UserLogin(SQLModel):
    email: str
    password: str