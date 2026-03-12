from typing import Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class InitRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    client_id: UUID = Field(validation_alias=AliasChoices("client_id", "clientId", "cliente_id", "clienteId"))
    brand_project: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("brand_project", "brandProject", "project"),
    )


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    text: str = Field(min_length=1, max_length=4000)
    client_id: UUID = Field(validation_alias=AliasChoices("client_id", "clientId", "cliente_id", "clienteId"))
    conversation_id: Optional[UUID] = Field(
        default=None, validation_alias=AliasChoices("conversation_id", "conversationId")
    )
    brand_project: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("brand_project", "brandProject", "project"),
    )
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    gclid: Optional[str] = None
    fbclid: Optional[str] = None
    ttclid: Optional[str] = None
    msclkid: Optional[str] = None
    li_fat_id: Optional[str] = None
    gbraid: Optional[str] = None
    wbraid: Optional[str] = None
    referrer_url: Optional[str] = None
    source_property_ref: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("source_property_ref", "property_id", "propertyId"),
    )
    landing_page_url: Optional[str] = None
    is_init: bool = False


class InternalMemoryResetRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    client_id: UUID = Field(validation_alias=AliasChoices("client_id", "clientId", "cliente_id", "clienteId"))
    reason: Optional[str] = None
