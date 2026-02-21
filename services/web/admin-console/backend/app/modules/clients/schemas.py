from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime

class ClientBase(BaseModel):
    name: str = Field(..., min_length=2, description="Nombre de la Empresa / Cliente")
    country_id: int = Field(..., description="ID del País")
    vertical_id: int = Field(..., description="ID del Vertical")
    scoring_model_id: Optional[UUID] = Field(None, description="Modelo de scoring asignado al cliente")

class ClientRow(ClientBase):
    """Schema for Display in Grid"""
    id: UUID
    country_name: Optional[str] = None
    vertical_name: Optional[str] = None
    scoring_model_name: Optional[str] = None
    # Optional fields in case we add them later to DB
    created_at: Optional[datetime] = None 
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ClientSimple(BaseModel):
    """Schema for Simple Dropdowns"""
    id: UUID
    name: str

class ClientCreate(ClientBase):
    """Schema for Creation Form"""
    pass

class ClientUpdate(BaseModel):
    """Schema for Update Form"""
    name: Optional[str] = Field(None, min_length=2)
    country_id: Optional[int] = Field(None)
    vertical_id: Optional[int] = Field(None)
    scoring_model_id: Optional[UUID] = Field(None)

class ClientStats(BaseModel):
    total_leads: int
    total_properties: int

class DocumentRow(BaseModel):
    id: int
    filename: str
    created_at: Optional[datetime]
    sync_status: str
