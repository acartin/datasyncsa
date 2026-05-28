import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Header, HTTPException, status

from app.core.config import get_settings
from app.core.db import get_connection
from app.repositories.auth_repository import AuthRepository


@dataclass(frozen=True)
class ClientContext:
    client_id: str
    client_name: str
    role: str
    role_label: str
    can_simulate_roles: bool
    is_role_simulated: bool
    user_id: str
    username: str
    email: str


VALID_ROLES = {
    "client-admin",
    "client-viewer",
    "system-admin",
    "system-user",
}


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session_token() -> str:
    return secrets.token_urlsafe(48)


def session_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(hours=12)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt, expected = password_hash.split("$", 3)
        iterations = int(iterations_raw)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    actual = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return hmac.compare_digest(actual, expected)


def make_password_hash(password: str) -> str:
    iterations = 260000
    salt = base64.urlsafe_b64encode(secrets.token_bytes(18)).decode("utf-8").rstrip("=")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    encoded = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return f"pbkdf2_sha256${iterations}${salt}${encoded}"


def require_client_context(
    authorization: str | None = Header(default=None),
) -> ClientContext:
    settings = get_settings()

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required",
        )

    repository = AuthRepository(get_connection)
    session = repository.session_context(token_hash=hash_token(token))
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    role = str(session["role"])
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid role context",
        )

    client_id = str(session.get("client_id") or "")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client context is required",
        )

    return ClientContext(
        client_id=client_id,
        client_name=str(session.get("client_name") or client_id),
        role=role,
        role_label=str(session.get("role_label") or role),
        can_simulate_roles=bool(session.get("can_simulate_roles")),
        is_role_simulated=bool(session.get("is_role_simulated")),
        user_id=str(session["user_id"]),
        username=str(session["username"]),
        email=str(session["email"]),
    )


def require_system_admin(context: ClientContext) -> ClientContext:
    if context.role != "system-admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System admin role is required",
        )
    return context
