from fastapi import APIRouter, Depends

from app.core.security import ClientContext, require_client_context
from app.domain.placeholders import module_payload


router = APIRouter()


@router.get("/campaigns")
def campaigns(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="operations.campaigns",
        title="Campaigns",
        description="Operational configuration for campaigns and target chains.",
        records=[
            {
                "id": "campaign-1",
                "name": "Sardimar atun competencia CR",
                "status": "active",
                "schedule": "daily",
            }
        ],
        actions=[
            {"id": "create-campaign", "label": "Create campaign", "enabled": context.role != "client-viewer"},
        ],
    )


@router.get("/catalogs")
def catalogs(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="operations.catalogs",
        title="Catalogs",
        description="Sources and catalogs associated with chains and locations.",
        records=[
            {"id": "walmart-family", "name": "Walmart family CR", "chains": 3, "status": "active"},
            {"id": "megasuper", "name": "Megasuper CR", "chains": 1, "status": "active"},
        ],
    )


@router.get("/monitored-products")
def monitored_products(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="operations.monitored-products",
        title="Monitored Products",
        description="Target products, GTINs and matching status.",
        records=[
            {"id": "sku-group-atun", "name": "Atun en conserva", "status": "in-review", "matches": 0},
        ],
    )


@router.get("/competitors")
def competitors(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="operations.competitors",
        title="Competitors",
        description="Active competitors by market and client.",
        records=[
            {"id": "masxmenos_cr", "name": "Mas x Menos", "market": "CR", "status": "active"},
            {"id": "maxi_pali_cr", "name": "Maxi Pali", "market": "CR", "status": "active"},
            {"id": "walmart_cr", "name": "Walmart", "market": "CR", "status": "active"},
            {"id": "megasuper_cr", "name": "Megasuper", "market": "CR", "status": "active"},
        ],
    )


@router.get("/runs")
def runs(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="operations.runs",
        title="Runs",
        description="Status of ETL executions orchestrated by Dagster.",
        records=[
            {"id": "dagster", "name": "Dagster", "status": "external", "url": "http://192.168.10.37:3010"},
        ],
        actions=[
            {"id": "open-dagster", "label": "Open Dagster", "enabled": True},
        ],
    )
