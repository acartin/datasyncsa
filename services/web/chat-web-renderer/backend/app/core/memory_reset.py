import asyncio
import logging
import os
from typing import Any, Dict

import httpx


logger = logging.getLogger("memory_reset")


class RuntimeMemoryResetError(RuntimeError):
    def __init__(self, *, failures: Dict[str, str], partial_results: Dict[str, Any]) -> None:
        self.failures = failures
        self.partial_results = partial_results
        message = "; ".join(f"{service}: {error}" for service, error in failures.items())
        super().__init__(message or "runtime_memory_reset_failed")


class MemoryResetClient:
    def __init__(self):
        self.agent_core_reset_url = os.getenv(
            "AI_RUNTIME_RESET_URL",
            os.getenv(
                "AGENT_CORE_RESET_URL",
                os.getenv(
                    "INFERENCE_RESET_URL",
                    os.getenv(
                        "INFERENCE_V2_RESET_URL",
                        "http://ai-runtime:8000/api/v1/internal/memory/reset",
                    ),
                ),
            ),
        ).rstrip("/")
        self.scoring_core_reset_url = self._resolve_scoring_reset_url()
        self.timeout = float(os.getenv("INFERENCE_TIMEOUT", 60))
        self.internal_token = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
        self.version = "runtime"

        logger.info(
            "MemoryResetClient configured (ai_runtime=%s scoring_core=%s version=%s)",
            self.agent_core_reset_url,
            self.scoring_core_reset_url,
            self.version,
        )

    @staticmethod
    def _resolve_scoring_reset_url() -> str:
        explicit_url = (os.getenv("SCORING_CORE_RESET_URL") or "").strip()
        if explicit_url:
            return explicit_url.rstrip("/")

        scoring_core_api = (os.getenv("SCORING_CORE_API") or "http://scoring-core:8000").strip().rstrip("/")
        prefix = (
            os.getenv("SCORING_API_PREFIX")
            or os.getenv("SCORING_CORE_API_PREFIX")
            or "/api/v1"
        ).strip()
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        prefix = prefix.rstrip("/")
        return f"{scoring_core_api}{prefix}/internal/memory/reset"

    @staticmethod
    def _format_error(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            response = exc.response
            body = response.text.strip()
            if len(body) > 250:
                body = f"{body[:247]}..."
            return f"HTTP {response.status_code} ({body})"
        return str(exc) or exc.__class__.__name__

    async def _post_reset(
        self,
        *,
        client: httpx.AsyncClient,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    async def reset_inference_memory(self, client_id: str, reason: str | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"client_id": client_id}
        if reason:
            payload["reason"] = reason

        headers: Dict[str, str] = {}
        if self.internal_token:
            headers["X-Internal-Token"] = self.internal_token

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await self._post_reset(
                client=client,
                url=self.agent_core_reset_url,
                payload=payload,
                headers=headers,
            )

    async def reset_runtime_session(
        self,
        *,
        client_id: str,
        session_id: str,
        reason: str | None = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "client_id": client_id,
            "session_id": session_id,
        }
        if reason:
            payload["reason"] = reason

        headers: Dict[str, str] = {}
        if self.internal_token:
            headers["X-Internal-Token"] = self.internal_token

        session_reset_url = self.agent_core_reset_url.replace(
            "/internal/memory/reset",
            "/internal/session/reset",
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await self._post_reset(
                client=client,
                url=session_reset_url,
                payload=payload,
                headers=headers,
            )

    async def reset_runtime_memory(self, client_id: str, reason: str | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"client_id": client_id}
        if reason:
            payload["reason"] = reason

        headers: Dict[str, str] = {}
        if self.internal_token:
            headers["X-Internal-Token"] = self.internal_token

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            agent_result, scoring_result = await asyncio.gather(
                self._post_reset(
                    client=client,
                    url=self.agent_core_reset_url,
                    payload=payload,
                    headers=headers,
                ),
                self._post_reset(
                    client=client,
                    url=self.scoring_core_reset_url,
                    payload=payload,
                    headers=headers,
                ),
                return_exceptions=True,
            )

        results: Dict[str, Any] = {}
        failures: Dict[str, str] = {}
        if isinstance(agent_result, Exception):
            failures["agent_core"] = self._format_error(agent_result)
        else:
            results["agent_core"] = agent_result

        if isinstance(scoring_result, Exception):
            failures["scoring_core"] = self._format_error(scoring_result)
        else:
            results["scoring_core"] = scoring_result

        if failures:
            raise RuntimeMemoryResetError(failures=failures, partial_results=results)

        return results
