from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

class GridPresetBase(BaseModel):
    name: str
    icon: Optional[str] = "📁"
    grid_id: str
    config: Dict[str, Any]
    is_default: Optional[bool] = False

class GridPresetCreate(GridPresetBase):
    pass

class GridPresetUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None

class GridPresetResponse(GridPresetBase):
    id: UUID
    user_id: UUID
    client_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
