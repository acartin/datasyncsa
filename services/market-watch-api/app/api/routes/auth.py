import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.db import get_connection
from app.core.security import VALID_ROLES, hash_token, make_password_hash, new_session_token, session_expiry, verify_password
from app.repositories.auth_repository import AuthRepository
from app.services.email_sender import EmailDeliveryError, send_password_reset_email


router = APIRouter()
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=240)


def get_repository() -> AuthRepository:
    return AuthRepository(get_connection)


def password_reset_expiry() -> datetime:
    settings = get_settings()
    return datetime.now(UTC) + timedelta(minutes=settings.password_reset_token_ttl_minutes)


@router.post("/login")
def login(payload: LoginRequest, repository: AuthRepository = Depends(get_repository)) -> dict[str, object]:
    user = repository.find_user_by_username(payload.username.strip())
    if not user or user["status"] != "active" or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = new_session_token()
    expires_at = session_expiry()
    repository.create_session(
        user_id=int(user["id"]),
        token_hash=hash_token(token),
        expires_at=expires_at.isoformat(),
        active_client_id=None,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at.astimezone(UTC).isoformat(),
    }


class ForgotPasswordRequest(BaseModel):
    login: str = Field(min_length=1, max_length=240)


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, repository: AuthRepository = Depends(get_repository)) -> dict[str, object]:
    settings = get_settings()
    user = repository.find_user_by_username(payload.login.strip())
    if not user or user["status"] != "active":
        return {"status": "ok"}

    token = new_session_token()
    token_hash = hash_token(token)
    expires_at = password_reset_expiry()
    repository.create_password_reset_token(
        user_id=int(user["id"]),
        delivery_email=str(user["email"]),
        token_hash=token_hash,
        expires_at=expires_at.isoformat(),
    )

    reset_link = f"{settings.web_base_url.rstrip('/')}/reset-password?token={token}"
    debug_reset_link = reset_link if settings.password_reset_debug_links else None
    if str(user["email"]).endswith(".local"):
        return {"status": "ok", "debug_reset_link": reset_link, "delivery": "debug"}

    try:
        send_password_reset_email(
            recipient_email=str(user["email"]),
            recipient_name=str(user.get("display_name") or user.get("username") or ""),
            reset_link=reset_link,
        )
    except EmailDeliveryError as exc:
        logger.warning("Password reset email delivery failed for %s: %s", user["email"], exc)
        if settings.password_reset_debug_links:
            return {"status": "ok", "debug_reset_link": reset_link, "delivery": "debug"}
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email could not be sent",
        ) from exc

    response: dict[str, object] = {"status": "ok"}
    if debug_reset_link:
        response["debug_reset_link"] = debug_reset_link
        response["delivery"] = "debug"
    return response


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=240)
    password: str = Field(min_length=8, max_length=240)


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, repository: AuthRepository = Depends(get_repository)) -> dict[str, str]:
    token_hash = hash_token(payload.token.strip())
    token_record = repository.find_password_reset_token(token_hash=token_hash)
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link is invalid or has expired",
        )

    consumed = repository.consume_password_reset_token(
        token_hash=token_hash,
        password_hash=make_password_hash(payload.password),
    )
    if not consumed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link is invalid or has expired",
        )

    return {"status": "ok"}


class LogoutRequest(BaseModel):
    token: str = Field(min_length=1)


@router.post("/logout")
def logout(payload: LogoutRequest, repository: AuthRepository = Depends(get_repository)) -> dict[str, str]:
    repository.revoke_session(token_hash=hash_token(payload.token))
    return {"status": "ok"}


class SimulateRoleRequest(BaseModel):
    role_id: str = Field(min_length=1, max_length=80)


@router.post("/simulate-role")
def simulate_role(
    payload: SimulateRoleRequest,
    authorization: str | None = Header(default=None),
    repository: AuthRepository = Depends(get_repository),
) -> dict[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")

    token_hash = hash_token(authorization.removeprefix("Bearer ").strip())
    if not repository.session_owner_can_simulate_roles(token_hash=token_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="System admin role is required")

    role_id = payload.role_id.strip()
    if role_id not in VALID_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

    repository.set_session_active_role(
        token_hash=token_hash,
        role_id=None if role_id == "system-admin" else role_id,
    )
    return {"status": "ok", "role_id": role_id}
