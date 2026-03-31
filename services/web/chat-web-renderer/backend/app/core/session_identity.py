from typing import Optional


_SESSION_ID_PLACEHOLDERS = {"init"}


def normalize_session_id(session_id: Optional[str]) -> Optional[str]:
    if session_id is None:
        return None
    value = str(session_id).strip()
    if not value:
        return None
    if value.lower() in _SESSION_ID_PLACEHOLDERS:
        return None
    return value


def normalize_optional_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def resolve_request_session_id(
    *,
    incoming_session_id: Optional[str],
    stored_session_id: Optional[str],
    incoming_conversation_id: Optional[str],
    stored_conversation_id: Optional[str],
) -> Optional[str]:
    return (
        normalize_session_id(incoming_session_id)
        or normalize_session_id(stored_session_id)
        or normalize_optional_id(incoming_conversation_id)
        or normalize_optional_id(stored_conversation_id)
    )


def resolve_effective_session_id(
    *,
    runtime_session_id: Optional[str],
    runtime_conversation_id: Optional[str],
    request_session_id: Optional[str],
    request_conversation_id: Optional[str],
) -> str:
    return (
        normalize_session_id(runtime_session_id)
        or normalize_session_id(request_session_id)
        or normalize_optional_id(runtime_conversation_id)
        or normalize_optional_id(request_conversation_id)
        or "init"
    )
