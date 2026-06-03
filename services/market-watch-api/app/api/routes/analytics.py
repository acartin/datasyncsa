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
        description="Superset dashboard catalog assigned to the client or role.",
        records=dashboard_records(),
        actions=[
            {"id": "open-superset", "label": "Open Superset", "enabled": True},
            {"id": "request-dashboard", "label": "Request dashboard", "enabled": False},
        ],
    )


@router.get("/reports")
def reports(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return module_payload(
        context=context,
        module_id="analytics.reports",
        title="Reports",
        description="Scheduled reports and future deliveries from Superset.",
        records=report_records(),
        actions=[
            {"id": "schedule-report", "label": "Schedule report", "enabled": False},
        ],
    )
