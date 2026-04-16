"""Load the human-editable realtor card CTA matrix from JSON."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

DEFAULT_CTA_MATRIX_PATH = "/app/schemas/realtor_card_cta_matrix.json"
_CACHE: dict[str, Any] | None = None


def load_realtor_card_cta_matrix(path: str | None = None) -> dict[str, Any]:
    global _CACHE
    if _CACHE is not None and path is None:
        return _CACHE

    matrix_path = Path(path or os.getenv("REALTOR_CARD_CTA_MATRIX_PATH", DEFAULT_CTA_MATRIX_PATH))
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    if path is None:
        _CACHE = payload
    logger.info("Loaded realtor CTA matrix from %s", matrix_path)
    return payload


def clear_realtor_card_cta_matrix_cache() -> None:
    global _CACHE
    _CACHE = None

