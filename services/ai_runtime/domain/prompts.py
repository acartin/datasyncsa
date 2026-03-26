"""Internal prompt payloads used by ai-runtime LLM integrations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PromptPayload(BaseModel):
    """Structured prompt split into stable and dynamic segments."""

    model_config = ConfigDict(extra="forbid")

    node_type: str
    stable_prefix: str
    dynamic_context: str
    full_prompt: str
    cacheable: bool = False
    cache_namespace: str | None = None
    cache_key: str | None = None
    cache_ttl_seconds: int = 0
    cache_metadata: dict[str, Any] = Field(default_factory=dict)

    def record_cache(self, **kwargs: Any) -> None:
        self.cache_metadata.update(kwargs)


PromptInput = str | PromptPayload
