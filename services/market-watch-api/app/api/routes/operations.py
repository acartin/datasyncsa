from fastapi import APIRouter, Depends

from app.core.security import ClientContext, require_client_context
from app.domain.placeholders import module_payload


router = APIRouter()


@router.get("/campaigns")
def campaigns(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="operations.campaigns",
        title="Campanas",
        description="Configuracion operativa de campanas y cadenas objetivo.",
        records=[
            {
                "id": "campaign-1",
                "name": "Sardimar atun competencia CR",
                "status": "active",
                "schedule": "daily",
            }
        ],
        actions=[
            {"id": "create-campaign", "label": "Crear campana", "enabled": context.role != "client-viewer"},
        ],
    )


@router.get("/catalogs")
def catalogs(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="operations.catalogs",
        title="Catalogos",
        description="Fuentes y catalogos asociados a cadenas y locations.",
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
        title="Productos monitoreados",
        description="Productos objetivo, GTINs y estado de matching.",
        records=[
            {"id": "sku-group-atun", "name": "Atun en conserva", "status": "in-review", "matches": 0},
        ],
    )


@router.get("/competitors")
def competitors(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="operations.competitors",
        title="Competidores",
        description="Competidores activos por mercado y cliente.",
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
        title="Corridas",
        description="Estado de ejecuciones ETL orquestadas por Dagster.",
        records=[
            {"id": "dagster", "name": "Dagster", "status": "external", "url": "http://192.168.10.37:3010"},
        ],
        actions=[
            {"id": "open-dagster", "label": "Abrir Dagster", "enabled": True},
        ],
    )
