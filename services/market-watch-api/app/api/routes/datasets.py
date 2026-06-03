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


@router.get("/executive-signals")
def executive_signals(
    campaign_id: Annotated[int | None, Query(ge=1)] = None,
    date_from: Annotated[str | None, Query(max_length=10)] = None,
    date_to: Annotated[str | None, Query(max_length=10)] = None,
    brand: Annotated[str | None, Query(max_length=160)] = None,
    chain: Annotated[str | None, Query(max_length=160)] = None,
    signal_type: Annotated[str | None, Query(max_length=120)] = None,
    severity: Annotated[str | None, Query(max_length=40)] = None,
    signal_status: Annotated[str | None, Query(max_length=80)] = None,
    q: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_repository),
) -> dict[str, object]:
    return repository.fetch_executive_signals(
        client_id=context.client_id,
        campaign_id=campaign_id,
        date_from=date_from,
        date_to=date_to,
        brand=brand,
        chain=chain,
        signal_type=signal_type,
        severity=severity,
        signal_status=signal_status,
        query=q,
        limit=limit,
        offset=offset,
    )


@router.get("/intraday-radar")
def intraday_radar(
    campaign_id: Annotated[int | None, Query(ge=1)] = None,
    date_key: Annotated[int | None, Query(ge=19000101, le=29991231)] = None,
    date_key_from: Annotated[int | None, Query(ge=19000101, le=29991231)] = None,
    date_key_to: Annotated[int | None, Query(ge=19000101, le=29991231)] = None,
    brand: Annotated[str | None, Query(max_length=160)] = None,
    chain: Annotated[str | None, Query(max_length=160)] = None,
    product_key: Annotated[str | None, Query(max_length=2000)] = None,
    event_area: Annotated[str | None, Query(max_length=40)] = None,
    severity: Annotated[str | None, Query(max_length=40)] = None,
    q: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_repository),
) -> dict[str, object]:
    return repository.fetch_intraday_radar(
        client_id=context.client_id,
        campaign_id=campaign_id,
        date_key=date_key,
        date_key_from=date_key_from,
        date_key_to=date_key_to,
        brand=brand,
        chain=chain,
        product_key=product_key,
        event_area=event_area,
        severity=severity,
        query=q,
        limit=limit,
        offset=offset,
    )


@router.get("/intraday-radar/products/{product_key}")
def intraday_product_detail(
    product_key: str,
    campaign_id: Annotated[int | None, Query(ge=1)] = None,
    date_key: Annotated[int | None, Query(ge=19000101, le=29991231)] = None,
    chain: Annotated[str | None, Query(max_length=160)] = None,
    history_days: Annotated[int, Query(ge=7, le=365)] = 30,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_repository),
) -> dict[str, object]:
    return repository.fetch_intraday_product_detail(
        client_id=context.client_id,
        product_key=product_key,
        campaign_id=campaign_id,
        date_key=date_key,
        chain=chain,
        history_days=history_days,
    )


@router.get("/executive-signals/{signal_id}")
def executive_signal_detail(
    signal_id: str,
    context: ClientContext = Depends(require_client_context),
    repository: MarketRepository = Depends(get_repository),
) -> dict[str, object]:
    return repository.fetch_signal_detail(
        client_id=context.client_id,
        signal_id=signal_id,
    )
