from fastapi import APIRouter, Depends

from app.core.security import ClientContext, require_client_context
from app.domain.placeholders import user_payload


router = APIRouter()


@router.get("")
def me(context: ClientContext = Depends(require_client_context)) -> dict[str, object]:
    return user_payload(context)
