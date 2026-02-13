from typing import Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class InitRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    client_id: UUID = Field(validation_alias=AliasChoices("client_id", "clientId"))


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    text: str = Field(min_length=1, max_length=4000)
    client_id: UUID = Field(validation_alias=AliasChoices("client_id", "clientId"))
    conversation_id: Optional[UUID] = Field(
        default=None, validation_alias=AliasChoices("conversation_id", "conversationId")
    )
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    source_property_ref: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("source_property_ref", "property_id", "propertyId"),
    )
    landing_page_url: Optional[str] = None
    is_init: bool = False
