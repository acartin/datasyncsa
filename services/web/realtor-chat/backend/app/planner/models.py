from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SQLIntent(str, Enum):
    NONE = "none"
    PROPERTY_INVENTORY = "property_inventory"
    PROPERTY_SEARCH = "property_search"
    PROPERTY_PRICE_RANGE = "property_price_range"


class SQLPlan(BaseModel):
    intent: SQLIntent = SQLIntent.NONE
    user_query: str
    effective_query: Optional[str] = None
    needs_clarification: bool = False
    clarification_message: Optional[str] = None


class SQLPlannerResult(BaseModel):
    handled: bool = False
    answer_override: Optional[str] = None
    components: List[Dict[str, Any]] = Field(default_factory=list)
    session_updates: Dict[str, Any] = Field(default_factory=dict)
