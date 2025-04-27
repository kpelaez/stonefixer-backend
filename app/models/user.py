from sqlmodel import SQLModel, Field
from datetime import datetime

class UserBase(SQLModel):
    email: str = Field(index=True, unique=True)
    full_name: str | None = None
    is_active: bool = True

class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password = str
    created_at: datetime = Field(default_factory=datetime.timestamp())
    updated_at: datetime = Field(default_factory=datetime.timestamp())

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    id: int
    created_at: datetime

class UserLogin(SQLModel):
    email: str
    password: str