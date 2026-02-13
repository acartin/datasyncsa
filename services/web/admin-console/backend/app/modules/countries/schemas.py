from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CountryRow(BaseModel):
    """Schema for Display in Grid"""
    id: int
    name: str
    iso_code: str
    updated_at: Optional[datetime] = None

class CountryCreate(BaseModel):
    """Schema for Creation Form"""
    name: str = Field(..., min_length=2, description="Full Name of the Country")
    iso_code: str = Field(..., min_length=2, max_length=2, description="2-letter ISO Code")

class CountryUpdate(BaseModel):
    """Schema for Update Form"""
    name: Optional[str] = Field(None, min_length=2)
    iso_code: Optional[str] = Field(None, min_length=2, max_length=2)
