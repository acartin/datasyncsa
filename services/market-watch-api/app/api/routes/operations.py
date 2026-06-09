import re
import unicodedata
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import errors
from pydantic import BaseModel, Field

from app.core.db import get_connection
from app.core.security import ClientContext, require_client_context
from app.domain.placeholders import module_payload
from app.repositories.market_repository import MarketRepository


router = APIRouter()

CAMPAIGN_EDITOR_ROLES = {"client-admin", "system-admin", "system-user"}
SYSTEM_OPERATOR_ROLES = {"system-admin", "system-user"}


def get_market_repository() -> MarketRepository:
    return MarketRepository(get_connection)


def require_system_operator(context: ClientContext) -> None:
    if context.role not in SYSTEM_OPERATOR_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System operations role is required",
        )


def require_campaign_editor(context: ClientContext) -> None:
    if context.role not in CAMPAIGN_EDITOR_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Campaign edit role is required",
        )


def normalize_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Campaign slug could not be generated",
        )
    return slug


class CampaignCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    slug: str | None = Field(default=None, max_length=180)
    description: str | None = Field(default=None, max_length=800)
    status: str = Field(default="active", pattern=r"^(active|inactive)$")
    access_role: str = Field(default="owner", pattern=r"^(viewer|owner|admin)$")
    is_default: bool = False


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    slug: str | None = Field(default=None, max_length=180)
    description: str | None = Field(default=None, max_length=800)
    status: str | None = Field(default=None, pattern=r"^(active|inactive)$")


class CampaignAccessUpsert(BaseModel):
    client_id: int = Field(ge=1)
    access_role: str = Field(default="viewer", pattern=r"^(viewer|owner|admin)$")
    is_default: bool = False
    is_active: bool = True
    valid_from: date | None = None
    valid_to: date | None = None


class CampaignAccessUpdate(BaseModel):
    access_role: str | None = Field(default=None, pattern=r"^(viewer|owner|admin)$")
    is_default: bool | None = None
    is_active: bool | None = None
    valid_from: date | None = None
    valid_to: date | None = None


class CampaignChainAssign(BaseModel):
    chain_key: int = Field(ge=1)


class CampaignStoreAssign(BaseModel):
    location_key: int = Field(ge=1)


class CampaignProductAssign(BaseModel):
    product_key: int | None = Field(default=None, ge=1)
    product_keys: list[int] = Field(default_factory=list)
    product_role: str = Field(default="tracked", pattern=r"^(owned|competitor|tracked|reference)$")


class CampaignProductUpdate(BaseModel):
    product_role: str | None = Field(default=None, pattern=r"^(owned|competitor|tracked|reference)$")


class CatalogSourceUpdate(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(enabled|disabled)$")


@router.get("/campaigns")
def campaigns(
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="operations.campaigns",
        title="Campaigns",
        description="Campaigns authorized for the active tenant, including products, locations and client access.",
        records=repository.list_campaigns_for_client(client_id=context.client_id),
        actions=[
            {"id": "create-campaign", "label": "Create campaign", "enabled": context.role in CAMPAIGN_EDITOR_ROLES},
            {"id": "configure-access", "label": "Configure access", "enabled": False},
        ],
    )


@router.post("/campaigns")
def create_campaign(
    payload: CampaignCreate,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    require_campaign_editor(context)
    slug = normalize_slug(payload.slug or payload.name)
    try:
        return repository.create_campaign(
            client_id=context.client_id,
            name=payload.name.strip(),
            slug=slug,
            description=payload.description,
            is_active=payload.status == "active",
            access_role=payload.access_role,
            is_default=payload.is_default,
        )
    except errors.UniqueViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A campaign with that slug already exists",
        ) from exc


@router.patch("/campaigns/{campaign_id}")
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    require_campaign_editor(context)
    slug = normalize_slug(payload.slug) if payload.slug else None
    try:
        campaign = repository.update_campaign(
            client_id=context.client_id,
            campaign_id=campaign_id,
            name=payload.name.strip() if payload.name else None,
            slug=slug,
            description=payload.description,
            is_active=None if payload.status is None else payload.status == "active",
            is_system_operator=context.role in SYSTEM_OPERATOR_ROLES,
        )
    except errors.UniqueViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A campaign with that slug already exists",
        ) from exc

    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found or not editable")
    return campaign


@router.get("/campaigns/{campaign_id}/workspace")
def campaign_workspace(
    campaign_id: int,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    workspace = repository.fetch_campaign_workspace(client_id=context.client_id, campaign_id=campaign_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return {
        "context": {
            "client_id": context.client_id,
            "role": context.role,
            "can_manage_access": context.role in SYSTEM_OPERATOR_ROLES,
        },
        "available_clients": repository.list_campaign_access_client_options()
        if context.role in SYSTEM_OPERATOR_ROLES
        else [],
        "available_chains": repository.list_campaign_chain_options()
        if context.role in SYSTEM_OPERATOR_ROLES
        else [],
        "available_stores": repository.list_campaign_store_options()
        if context.role in SYSTEM_OPERATOR_ROLES
        else [],
        "available_products": repository.list_campaign_product_options()
        if context.role in SYSTEM_OPERATOR_ROLES
        else [],
        **workspace,
    }


@router.post("/campaigns/{campaign_id}/access")
def assign_campaign_access(
    campaign_id: int,
    payload: CampaignAccessUpsert,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    require_system_operator(context)
    try:
        access = repository.upsert_campaign_client_access(
            campaign_id=campaign_id,
            client_id=payload.client_id,
            access_role=payload.access_role,
            is_default=payload.is_default,
            is_active=payload.is_active,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
        )
    except errors.ForeignKeyViolation as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign or client not found") from exc
    if not access:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign or client not found")
    return access


@router.patch("/campaigns/{campaign_id}/access/{client_id}")
def update_campaign_access(
    campaign_id: int,
    client_id: int,
    payload: CampaignAccessUpdate,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    require_system_operator(context)
    access = repository.update_campaign_client_access(
        campaign_id=campaign_id,
        client_id=client_id,
        access_role=payload.access_role,
        is_default=payload.is_default,
        is_active=payload.is_active,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
    )
    if not access:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign access not found")
    return access


@router.post("/campaigns/{campaign_id}/chains")
def assign_campaign_chain(
    campaign_id: int,
    payload: CampaignChainAssign,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    require_system_operator(context)
    result = repository.assign_campaign_chain(campaign_id=campaign_id, chain_key=payload.chain_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign or chain not found")
    if result.get("assigned_locations") == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Chain has no active stores to assign")
    return result


@router.delete("/campaigns/{campaign_id}/chains/{chain_key}")
def remove_campaign_chain(
    campaign_id: int,
    chain_key: int,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    require_system_operator(context)
    result = repository.remove_campaign_chain(campaign_id=campaign_id, chain_key=chain_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign or chain not found")
    return result


@router.post("/campaigns/{campaign_id}/stores")
def assign_campaign_store(
    campaign_id: int,
    payload: CampaignStoreAssign,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    require_system_operator(context)
    result = repository.assign_campaign_store(campaign_id=campaign_id, location_key=payload.location_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign or store not found")
    return result


@router.delete("/campaigns/{campaign_id}/stores/{location_key}")
def remove_campaign_store(
    campaign_id: int,
    location_key: int,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    require_system_operator(context)
    result = repository.remove_campaign_store(campaign_id=campaign_id, location_key=location_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign or store not found")
    return result


@router.post("/campaigns/{campaign_id}/products")
def assign_campaign_product(
    campaign_id: int,
    payload: CampaignProductAssign,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    require_system_operator(context)
    product_keys = [*payload.product_keys]
    if payload.product_key is not None:
        product_keys.append(payload.product_key)
    product_keys = sorted(set(product_keys))
    if not product_keys:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select at least one product")

    assigned = []
    for product_key in product_keys:
        result = repository.assign_campaign_product(
            campaign_id=campaign_id,
            product_key=product_key,
            product_role=payload.product_role,
        )
        if result:
            assigned.append(result)

    if not assigned:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign or product not found")
    return {"assigned": assigned, "assigned_count": len(assigned)}


@router.patch("/campaigns/{campaign_id}/products/{product_key}")
def update_campaign_product(
    campaign_id: int,
    product_key: int,
    payload: CampaignProductUpdate,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    require_system_operator(context)
    result = repository.update_campaign_product(
        campaign_id=campaign_id,
        product_key=product_key,
        product_role=payload.product_role,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign product not found")
    return result


@router.delete("/campaigns/{campaign_id}/products/{product_key}")
def remove_campaign_product(
    campaign_id: int,
    product_key: int,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    require_system_operator(context)
    result = repository.remove_campaign_product(campaign_id=campaign_id, product_key=product_key)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign or product not found")
    return result


@router.get("/campaign-access")
def campaign_access(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    require_system_operator(context)
    return module_payload(
        context=context,
        module_id="operations.campaign-access",
        title="Campaign Access",
        description="Placeholder for tenant visibility, edit rights and default campaign assignment.",
        records=[
            {
                "id": "campaign-client-access",
                "name": "Tenant campaign access",
                "source": "mkt_campaign_client_access",
                "status": "planned",
                "owner": "system operations",
            },
            {
                "id": "default-campaign",
                "name": "Default campaign per tenant",
                "source": "mkt_campaign_client_access.is_default",
                "status": "planned",
                "owner": "system operations",
            },
        ],
        actions=[
            {"id": "create-access", "label": "Add access", "enabled": False},
        ],
    )


@router.get("/monitored-products")
def monitored_products(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    require_system_operator(context)
    return module_payload(
        context=context,
        module_id="operations.monitored-products",
        title="Monitored Products",
        description="Placeholder for products, GTINs and matching status assigned to campaigns.",
        records=[
            {
                "id": "campaign-products",
                "name": "Campaign product assignment",
                "source": "mkt_campaign_product",
                "status": "planned",
                "owner": "system operations",
            },
            {
                "id": "product-matching",
                "name": "Catalog product matching",
                "source": "mkt_dim_product",
                "status": "planned",
                "owner": "pricing operations",
            },
        ],
        actions=[
            {"id": "add-product", "label": "Add product", "enabled": False},
        ],
    )


@router.get("/locations-chains")
def locations_chains(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    require_system_operator(context)
    return module_payload(
        context=context,
        module_id="operations.locations-chains",
        title="Locations & Chains",
        description="Placeholder for chains, stores and monitored market locations.",
        records=[
            {
                "id": "campaign-locations",
                "name": "Campaign location assignment",
                "source": "mkt_campaign_location",
                "status": "planned",
                "owner": "system operations",
            },
            {
                "id": "chain-directory",
                "name": "Chain and store directory",
                "source": "mkt_dim_chain / mkt_dim_location",
                "status": "planned",
                "owner": "pricing operations",
            },
        ],
        actions=[
            {"id": "add-location", "label": "Add location", "enabled": False},
        ],
    )


@router.get("/catalog-sources")
def catalog_sources(
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    require_system_operator(context)
    return module_payload(
        context=context,
        module_id="operations.catalog-sources",
        title="Catalog Sources",
        description="Root category configuration used by catalog extraction before canonical product loading.",
        status="active",
        records=repository.list_catalog_sources(),
        actions=[
            {"id": "refresh-categories", "label": "Refresh in Dagster", "enabled": False},
        ],
    )


@router.patch("/catalog-sources/{category_key}")
def update_catalog_source(
    category_key: int,
    payload: CatalogSourceUpdate,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_market_repository),
) -> dict[str, object]:
    require_system_operator(context)
    category = repository.update_catalog_source(
        category_key=category_key,
        is_enabled=None if payload.status is None else payload.status == "enabled",
    )
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog source not found")
    return category


@router.get("/runs-jobs")
def runs_jobs(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    require_system_operator(context)
    return module_payload(
        context=context,
        module_id="operations.runs-jobs",
        title="Runs & Jobs",
        description="Status of ETL executions orchestrated by Dagster.",
        records=[
            {"id": "dagster", "name": "Dagster", "status": "external", "url": "http://192.168.10.37:3010"},
            {"id": "mkt-run", "name": "Run history", "status": "planned", "source": "mkt_run"},
        ],
        actions=[
            {"id": "open-dagster", "label": "Open Dagster", "enabled": True},
        ],
    )


@router.get("/data-quality")
def data_quality(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    require_system_operator(context)
    return module_payload(
        context=context,
        module_id="operations.data-quality",
        title="Data Quality",
        description="Placeholder for freshness, coverage gaps and operational data checks.",
        records=[
            {
                "id": "freshness",
                "name": "Freshness by campaign",
                "source": "mkt_run / semantic views",
                "status": "planned",
                "owner": "data operations",
            },
            {
                "id": "coverage",
                "name": "Product and location coverage",
                "source": "mkt_campaign_product / mkt_campaign_location",
                "status": "planned",
                "owner": "pricing operations",
            },
            {
                "id": "exceptions",
                "name": "Pricing exceptions",
                "source": "facts and validation checks",
                "status": "planned",
                "owner": "data operations",
            },
        ],
    )
