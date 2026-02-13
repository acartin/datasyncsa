from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False

class UserCreate(UserBase):
    password: str
    client_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    contact_id: Optional[UUID] = None

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    client_id: Optional[UUID] = None
    role_id: Optional[UUID] = None

class UserRow(UserBase):
    id: UUID
    role_name: Optional[str] = None
    role_slug: Optional[str] = None
    client_name: Optional[str] = None
    client_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    contact_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)
