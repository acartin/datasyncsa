from fastapi import APIRouter, Depends

from app.core.security import ClientContext, require_client_context
from app.domain.placeholders import dashboard_records, module_payload, report_records


router = APIRouter()


@router.get("/dashboards")
def dashboards(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="analytics.dashboards",
        title="Dashboards",
        description="Catalogo de dashboards Superset asignados al cliente o rol.",
        records=dashboard_records(),
        actions=[
            {"id": "open-superset", "label": "Abrir Superset", "enabled": True},
            {"id": "request-dashboard", "label": "Solicitar dashboard", "enabled": False},
        ],
    )


@router.get("/reports")
def reports(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="analytics.reports",
        title="Reportes",
        description="Reportes programados y entregas futuras desde Superset.",
        records=report_records(),
        actions=[
            {"id": "schedule-report", "label": "Programar reporte", "enabled": False},
        ],
    )
