from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime

class PromptBase(BaseModel):
    """Shared properties"""
    slug: str = Field(..., min_length=3, description="Unique identifier/name for the prompt")
    prompt_text: str = Field(..., min_length=10, description="The actual prompt content")
    is_active: bool = Field(True, description="Whether this prompt is active")

class PromptCreate(PromptBase):
    """Schema for Creation - client_id can be provided by admin or inferred"""
    client_id: Optional[UUID] = None

class PromptUpdate(BaseModel):
    """Schema for Update - all fields optional"""
    slug: Optional[str] = Field(None, min_length=3)
    prompt_text: Optional[str] = Field(None, min_length=10)
    is_active: Optional[bool] = Field(None)
    client_id: Optional[UUID] = None

class PromptRow(PromptBase):
    """Schema for Grid Display"""
    id: UUID
    client_name: Optional[str] = None # For Admin view
    client_id: Optional[UUID] = None
    updated_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)
