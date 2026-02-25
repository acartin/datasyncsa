from typing import Optional, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class VerticalRow(BaseModel):
    id: int
    name: str
    slug: str


class VerticalCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=2, max_length=100)


class VerticalUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    slug: Optional[str] = Field(default=None, min_length=2, max_length=100)


class ScoringModelRow(BaseModel):
    id: UUID
    vertical_id: int
    vertical_name: Optional[str] = None
    name: str
    version: int
    prompt_version: int
    is_active: bool
    normalization_strategy: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ScoringModelCreate(BaseModel):
    vertical_id: int
    name: str = Field(..., min_length=2, max_length=128)
    version: int = Field(default=1, gt=0)
    prompt_version: int = Field(default=1, gt=0)
    is_active: bool = True
    normalization_strategy: Optional[str] = Field(default=None, max_length=64)


class ScoringModelUpdate(BaseModel):
    vertical_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=2, max_length=128)
    version: Optional[int] = Field(default=None, gt=0)
    prompt_version: Optional[int] = Field(default=None, gt=0)
    is_active: Optional[bool] = None
    normalization_strategy: Optional[str] = Field(default=None, max_length=64)


class ScoringCriterionRow(BaseModel):
    id: UUID
    model_id: UUID
    model_name: Optional[str] = None
    vertical_name: Optional[str] = None
    criterion_key: str
    label: str
    weight: float
    min_score: float
    max_score: float
    display_order: int
    icon: Optional[str] = None
    is_active: bool


class ScoringCriterionCreate(BaseModel):
    model_id: UUID
    criterion_key: str = Field(..., min_length=2, max_length=64)
    label: str = Field(..., min_length=2, max_length=128)
    weight: float = Field(default=1.0, ge=0.0)
    min_score: float = 0.0
    max_score: float = 10.0
    display_order: int = Field(default=0, ge=0)
    icon: Optional[str] = Field(default=None, max_length=128)
    is_active: bool = True


class ScoringCriterionUpdate(BaseModel):
    model_id: Optional[UUID] = None
    label: Optional[str] = Field(default=None, min_length=2, max_length=128)
    weight: Optional[float] = Field(default=None, ge=0.0)
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    display_order: Optional[int] = Field(default=None, ge=0)
    icon: Optional[str] = Field(default=None, max_length=128)
    is_active: Optional[bool] = None


class ScoringBandRow(BaseModel):
    id: UUID
    criterion_id: UUID
    criterion_key: Optional[str] = None
    model_name: Optional[str] = None
    band_key: str
    label: str
    min_score: float
    max_score: float
    icon: Optional[str] = None
    color: Optional[str] = None


class ScoringBandCreate(BaseModel):
    criterion_id: UUID
    band_key: str = Field(..., min_length=2, max_length=32)
    label: str = Field(..., min_length=2, max_length=64)
    min_score: float
    max_score: float
    icon: Optional[str] = Field(default=None, max_length=128)
    color: Optional[str] = Field(default=None, max_length=32)


class ScoringBandUpdate(BaseModel):
    criterion_id: Optional[UUID] = None
    band_key: Optional[str] = Field(default=None, min_length=2, max_length=32)
    label: Optional[str] = Field(default=None, min_length=2, max_length=64)
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    icon: Optional[str] = Field(default=None, max_length=128)
    color: Optional[str] = Field(default=None, max_length=32)


class ScoringPromptRow(BaseModel):
    id: UUID
    model_id: UUID
    model_name: Optional[str] = None
    version: int
    prompt_template: str
    extraction_schema_legacy: Optional[Any] = None
    is_active: bool
    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ScoringPromptCreate(BaseModel):
    model_id: UUID
    version: int = Field(..., gt=0)
    prompt_template: str = Field(..., min_length=10)
    is_active: bool = True


class ScoringPromptUpdate(BaseModel):
    model_id: Optional[UUID] = None
    version: Optional[int] = Field(default=None, gt=0)
    prompt_template: Optional[str] = Field(default=None, min_length=10)
    is_active: Optional[bool] = None
