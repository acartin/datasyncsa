from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict

# --- Channel Schemas ---
class ChannelBase(BaseModel):
    category_id: int
    value: str
    label: Optional[str] = None
    is_primary: bool = False

class ChannelCreate(ChannelBase):
    type: Optional[str] = "other" # Frontend usually doesn't send this

class ChannelRead(ChannelBase):
    id: UUID
    contact_id: UUID
    type: str # Required in Read
    category_name: Optional[str] = None
    category_icon: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- Contact Schemas ---
class ContactBase(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    position: Optional[str] = None
    is_active: bool = True

class ContactCreate(ContactBase):
    client_id: Optional[UUID] = None  # Super Admins must provide this
    channels: Optional[List[ChannelCreate]] = []

class ContactUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    position: Optional[str] = None
    is_active: Optional[bool] = None
    channels: Optional[List[ChannelCreate]] = None

class ContactRead(ContactBase):
    id: UUID
    client_id: UUID
    created_at: datetime
    updated_at: datetime
    channels: List[ChannelRead] = []

    model_config = ConfigDict(from_attributes=True)

class ContactConvert(BaseModel):
    email: EmailStr
    password: str
