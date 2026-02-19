from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID

class ScoringBandV2(BaseModel):
    """Visual band configuration for scoring"""
    band_key: str = Field(..., description="Band identifier (e.g., low, medium, high, critical)")
    label: str = Field(..., description="Display label for the band")
    min_score: float = Field(..., description="Minimum score (inclusive)")
    max_score: float = Field(..., description="Maximum score (exclusive)")
    icon: Optional[str] = Field(None, description="Icon class or name")
    color: Optional[str] = Field(None, description="CSS color for visualization")


class ScoringCriterionV2(BaseModel):
    """Dynamic scoring criterion"""
    criterion_key: str = Field(..., description="Criterion identifier (e.g., intent, urgency, data_quality)")
    label: str = Field(..., description="Display label for the criterion")
    weight: float = Field(..., ge=0.0, le=1.0, description="Weight in total score calculation (0-1)")
    min_score: float = Field(..., description="Minimum possible score")
    max_score: float = Field(..., description="Maximum possible score")
    display_order: int = Field(..., ge=0, description="Order for UI display")
    bands: List[ScoringBandV2] = Field(default_factory=list, description="Visual bands for this criterion")


class ScoringSchemaV2(BaseModel):
    """Dynamic scoring schema for a lead type"""
    model_config = {"populate_by_name": True}
    
    lead_type: str = Field(..., description="Type of lead (e.g., realtor, medico, dental, automotriz)")
    model_id: UUID = Field(..., description="Active model ID")
    model_version: int = Field(..., gt=0, description="Model version")
    prompt_version: int = Field(..., gt=0, description="Prompt version")
    criteria: List[ScoringCriterionV2] = Field(default_factory=list, description="Active criteria for this lead type")
    normalization_strategy: Optional[str] = Field(None, description="Strategy for score normalization")


class ScoreItemValueV2(BaseModel):
    """Individual criterion score with visual metadata"""
    criterion_key: str = Field(..., description="Criterion identifier")
    score: float = Field(..., ge=0.0, description="Actual score")
    band_key: Optional[str] = Field(None, description="Matching band key")
    band_label: Optional[str] = Field(None, description="Matching band label")
    band_color: Optional[str] = Field(None, description="Matching band color")
    band_icon: Optional[str] = Field(None, description="Matching band icon")
    explanation: Optional[str] = Field(None, description="Explanation for this score")
    normalized_score: Optional[float] = Field(None, description="Normalized score (0-100)")


class ScoringValuesV2(BaseModel):
    """Actual scoring values for a lead"""
    model_config = {"populate_by_name": True, "extra": "allow"}
    
    score_total: float = Field(..., ge=0.0, description="Total normalized score")
    priority_label: Optional[str] = Field(None, description="Derived priority label")
    reasoning: Optional[str] = Field(None, description="Overall scoring reasoning")
    score_items: List[ScoreItemValueV2] = Field(default_factory=list, description="Individual criterion scores")
    scorecard_id: Optional[UUID] = Field(None, description="Scorecard ID for reference")
    created_at: Optional[str] = Field(None, description="Scorecard creation timestamp")


class DynamicLeadGridColumn(BaseModel):
    """Dynamic column definition for grid based on scoring schema"""
    id: str = Field(..., description="Column identifier")
    label: str = Field(..., description="Display label")
    type: str = Field("scoring-pillar", description="Column type (scoring-pillar, gauge-identity, etc.)")
    sortable: bool = Field(True, description="Whether column is sortable")
    width: Optional[str] = Field(None, description="CSS width")
    icon: Optional[str] = Field(None, description="Icon for column header")
    criterion_key: Optional[str] = Field(None, description="Associated criterion key for scoring columns")


class DynamicGridConfig(BaseModel):
    """Dynamic grid configuration based on scoring schema"""
    grid_id: str = Field(..., description="Grid identifier")
    data_url: str = Field(..., description="URL for grid data")
    enable_filters: bool = Field(True, description="Whether filters are enabled")
    columns: List[DynamicLeadGridColumn] = Field(default_factory=list, description="Dynamic columns")
    filter_config: Optional[Dict[str, Any]] = Field(None, description="Filter configuration")
    actions: List[Dict[str, Any]] = Field(default_factory=list, description="Grid actions")
