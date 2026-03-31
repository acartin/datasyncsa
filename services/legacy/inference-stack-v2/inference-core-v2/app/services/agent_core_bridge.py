from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID, uuid4

import httpx

from app.core.config import settings
from app.models.chat_v2 import ChatV2Request, ChatV2Response

logger = logging.getLogger("inference-core-v2.agent-core-bridge")


_CHANNELS = {"web_html", "meta_whatsapp", "meta_ig", "api"}
_INTENT_MAP = {
    "realtor_search": "PROPERTY_SEARCH",
    "realtor_refine": "PROPERTY_SEARCH",
    "rag": "RAG",
    "clarify": "CLARIFICATION",
    "workflow": "WORKFLOW",
    "answer": "ANSWER",
}


class AgentCoreBridgeError(Exception):
    def __init__(self, *, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail)


def _coerce_uuid(raw: Any, fallback: UUID | None = None) -> UUID:
    if isinstance(raw, UUID):
        return raw
    if raw is None:
        return fallback or uuid4()
    try:
        return UUID(str(raw))
    except Exception:
        return fallback or uuid4()


def _coerce_optional_uuid(raw: Any) -> UUID | None:
    if raw is None:
        return None
    if isinstance(raw, UUID):
        return raw
    try:
        return UUID(str(raw))
    except Exception:
        return None


def _normalize_scoring_status(raw: Any) -> str | None:
    token = str(raw or "").strip().lower()
    if not token:
        return None
    if token in {"pending", "queued", "processing"}:
        return "pending"
    if token == "error":
        return "error"
    if token == "disabled":
        return "disabled"
    return token


def _normalize_intent(raw: Any) -> str | None:
    if raw is None:
        return None
    token = str(raw).strip()
    if not token:
        return None
    mapped = _INTENT_MAP.get(token.lower())
    if mapped:
        return mapped
    return token.upper()


def _resolve_channel(user_metadata: dict[str, Any] | None) -> str:
    if not isinstance(user_metadata, dict):
        return "web_html"
    for key in ("channel", "channel_slug", "channel_type"):
        value = user_metadata.get(key)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in _CHANNELS:
                return normalized
    return "web_html"


def _normalize_components(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            normalized.append(item)
    return normalized


def _split_text_for_card_flow(text: str) -> tuple[str, str]:
    base_text = (text or "").strip()
    if not base_text:
        return "", ""
    blocks = [block.strip() for block in re.split(r"\n\s*\n+", base_text) if block.strip()]
    if len(blocks) > 1:
        return blocks[0], "\n\n".join(blocks[1:])

    sentences = [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+", base_text) if chunk.strip()]
    if len(sentences) <= 1:
        return base_text, ""
    return " ".join(sentences[:-1]).strip(), sentences[-1]


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            detail = payload.get("detail") or payload.get("error")
            if detail:
                return str(detail)
            return str(payload)
    except Exception:
        pass
    text = (response.text or "").strip()
    if text:
        return text
    return f"Upstream agent-core error ({response.status_code})"


class AgentCoreBridge:
    def __init__(self) -> None:
        self.base_url = settings.agent_core_api.rstrip("/")
        self.api_prefix = settings.agent_core_api_prefix
        self.chat_url = f"{self.base_url}{self.api_prefix}/chat"
        self.timeout_secs = float(settings.agent_core_timeout_secs)
        self.connect_timeout_secs = float(settings.agent_core_connect_timeout_secs)

    def _to_agent_payload(self, request: ChatV2Request) -> dict[str, Any]:
        user_metadata = request.user_metadata or {}
        lead_id = user_metadata.get("lead_id")
        if lead_id is None:
            lead_id = user_metadata.get("leadId")
        payload: dict[str, Any] = {
            "clientId": str(request.client_id),
            "queryText": request.query_text,
            "conversationId": str(request.conversation_id) if request.conversation_id else None,
            "channel": _resolve_channel(user_metadata),
            "filters": request.filters or {},
            "userMetadata": user_metadata,
            "leadId": str(lead_id) if isinstance(lead_id, (str, UUID)) else None,
        }
        return {key: value for key, value in payload.items() if value is not None}

    @staticmethod
    def _to_v2_response(data: dict[str, Any], fallback_conversation_id: UUID | None) -> ChatV2Response:
        answer_text = str(data.get("answer") or "")
        components = _normalize_components(data.get("components"))
        if components and answer_text:
            pre_text, post_text = _split_text_for_card_flow(answer_text)
            answer_text = pre_text or answer_text
            if post_text:
                components.append(
                    {
                        "type": "chat_text",
                        "text": post_text,
                        "sender": "bot",
                    }
                )

        return ChatV2Response(
            answer=answer_text,
            intent=_normalize_intent(data.get("intent")),
            realtor_turn=None,
            components=components,
            conversation_id=_coerce_uuid(
                data.get("conversationId") or data.get("conversation_id"),
                fallback=fallback_conversation_id,
            ),
            lead_id=_coerce_optional_uuid(data.get("leadId") or data.get("lead_id")),
            scorecard_id=None,
            scorecard=None,
            scoring_status=_normalize_scoring_status(
                data.get("scoringStatus") or data.get("scoring_status")
            ),
            scoring_job_id=_coerce_optional_uuid(
                data.get("scoringJobId") or data.get("scoring_job_id")
            ),
            scoring_eta=(
                str(data.get("scoringEta") or data.get("scoring_eta"))
                if (data.get("scoringEta") or data.get("scoring_eta"))
                else None
            ),
        )

    async def chat(self, request: ChatV2Request) -> ChatV2Response:
        payload = self._to_agent_payload(request)
        timeout = httpx.Timeout(timeout=self.timeout_secs, connect=self.connect_timeout_secs)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.chat_url, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AgentCoreBridgeError(
                status_code=504,
                detail="agent-core timeout while processing chat request",
            ) from exc
        except httpx.HTTPStatusError as exc:
            upstream_status = int(exc.response.status_code)
            raise AgentCoreBridgeError(
                status_code=upstream_status if upstream_status < 500 else 502,
                detail=_extract_error_detail(exc.response),
            ) from exc
        except httpx.RequestError as exc:
            raise AgentCoreBridgeError(
                status_code=503,
                detail=f"agent-core unavailable: {exc}",
            ) from exc

        data = response.json() if response.content else {}
        if not isinstance(data, dict):
            raise AgentCoreBridgeError(
                status_code=502,
                detail="invalid upstream payload from agent-core",
            )
        return self._to_v2_response(data, fallback_conversation_id=request.conversation_id)


agent_core_bridge = AgentCoreBridge()
