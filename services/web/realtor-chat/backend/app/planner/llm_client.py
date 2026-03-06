from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger("sql_planner_llm")


class GeminiPlannerLLMClient:
    """Thin adapter matching SQLPlanner's expected `complete(system, messages)` API."""

    def __init__(self, api_key: str, model: str, timeout_secs: int = 30):
        self.model = model
        self.timeout_secs = max(1, int(timeout_secs or 30))
        self._client = None
        self._api_key = api_key

    @property
    def client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    @staticmethod
    def _compose_user_prompt(messages: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for message in messages or []:
            role = str(message.get("role") or "user").strip().lower()
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            lines.append(f"{role}: {content}")
        return "\n".join(lines).strip() or "user: {}"

    async def complete(self, system: str, messages: List[Dict[str, Any]]) -> str:
        from google.genai import types

        user_prompt = self._compose_user_prompt(messages)
        response = await asyncio.wait_for(
            asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=[user_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.1,
                    max_output_tokens=512,
                ),
            ),
            timeout=self.timeout_secs,
        )
        return (response.text or "").strip()


def build_sql_planner_llm_client() -> GeminiPlannerLLMClient | None:
    api_key = (os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        logger.warning("SQLPlanner LLM disabled: GOOGLE_API_KEY not configured")
        return None

    model = (os.getenv("LLM_MODEL") or "gemini-2.5-flash-lite").strip()
    timeout_secs = int(os.getenv("LLM_TIMEOUT_SECS") or "30")

    try:
        # Fail fast if dependency is missing.
        from google import genai  # noqa: F401
    except ImportError:
        logger.warning("SQLPlanner LLM disabled: google-genai not installed")
        return None

    logger.info("SQLPlanner LLM enabled with model=%s timeout=%ss", model, timeout_secs)
    return GeminiPlannerLLMClient(api_key=api_key, model=model, timeout_secs=timeout_secs)

