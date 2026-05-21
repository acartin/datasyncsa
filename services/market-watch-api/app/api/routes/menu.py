from fastapi import APIRouter, Depends

from app.core.security import ClientContext, require_client_context
from app.domain.placeholders import menu_payload


router = APIRouter()


@router.get("")
def menu(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return menu_payload(context)
