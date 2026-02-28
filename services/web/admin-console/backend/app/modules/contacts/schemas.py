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


class ContactGridRow(BaseModel):
    id: UUID
    first_name: str
    last_name: Optional[str] = None
    name: str
    full_name: str
    position: Optional[str] = None
    primary_channel: str = "-"
    primary_email: Optional[str] = None
    channels_count: int = 0
    is_active: str = "false"


class ContactChannelManageBase(BaseModel):
    category_id: Optional[int] = None
    type: str = "other"
    value: str
    label: Optional[str] = None
    is_primary: bool = False
    is_verified: bool = False


class ContactChannelManageCreate(ContactChannelManageBase):
    pass


class ContactChannelManageUpdate(BaseModel):
    category_id: Optional[int] = None
    type: Optional[str] = None
    value: Optional[str] = None
    label: Optional[str] = None
    is_primary: Optional[bool] = None
    is_verified: Optional[bool] = None


class ContactChannelManageRow(BaseModel):
    id: UUID
    contact_id: UUID
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    category_icon: Optional[str] = None
    type: str
    value: str
    label: Optional[str] = None
    is_primary: str = "false"
    is_verified: str = "false"


class ContactChannelListRow(BaseModel):
    id: UUID
    contact_id: UUID
    contact_name: str
    category_icon: Optional[str] = None
    category_name: Optional[str] = None
    type: str
    value: str
    label: Optional[str] = None
    is_primary: str = "false"
    is_verified: str = "false"
