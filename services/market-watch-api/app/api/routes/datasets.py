from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.db import get_connection
from app.core.security import ClientContext, require_client_context
from app.repositories.market_repository import MarketRepository


router = APIRouter()


def get_repository() -> MarketRepository:
    return MarketRepository(get_connection)


@router.get("/overview")
def overview(
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_repository),
) -> dict[str, object]:
    return repository.fetch_overview(client_id=context.client_id)


@router.get("/products")
def products(
    q: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_repository),
) -> dict[str, object]:
    return repository.fetch_products(
        client_id=context.client_id,
        query=q,
        limit=limit,
        offset=offset,
    )


@router.get("/price-matrix")
def price_matrix(
    campaign_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_repository),
) -> dict[str, object]:
    return repository.fetch_price_matrix(
        client_id=context.client_id,
        campaign_id=campaign_id,
        limit=limit,
    )
