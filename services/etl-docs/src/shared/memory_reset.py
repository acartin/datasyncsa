import logging
import os
from typing import Optional

import requests


logger = logging.getLogger(__name__)


def reset_client_memory(client_id: str, reason: Optional[str] = None) -> bool:
    """
    Best-effort call to reset downstream chat memory after knowledge mutations.
    Does not raise to avoid breaking ETL lifecycle operations.
    """
    reset_url = (os.getenv("MEMORY_RESET_URL") or "").strip().rstrip("/")
    if not reset_url:
        logger.info("MEMORY_RESET_URL not configured; skipping memory reset for client %s", client_id)
        return False

    payload = {"client_id": client_id}
    if reason:
        payload["reason"] = reason

    headers = {}
    token = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
    if token:
        headers["X-Internal-Token"] = token

    timeout = float(os.getenv("MEMORY_RESET_TIMEOUT", "8"))
    try:
        response = requests.post(reset_url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        logger.info("Memory reset triggered for client %s", client_id)
        return True
    except Exception as exc:
        logger.warning("Memory reset failed for client %s: %s", client_id, exc)
        return False
