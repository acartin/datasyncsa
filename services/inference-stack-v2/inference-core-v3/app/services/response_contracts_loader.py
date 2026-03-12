from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict

from app.core.config import settings


class ResponseContractsLoader:
    @lru_cache(maxsize=1)
    def load(self) -> Dict[str, Any]:
        with open(settings.response_contracts_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("response contracts root must be an object")
        return data

    def get_section(self, section_name: str) -> Dict[str, Any]:
        section = self.load().get(section_name) or {}
        if not isinstance(section, dict):
            raise ValueError(f"response contracts section '{section_name}' must be an object")
        return section


response_contracts_loader = ResponseContractsLoader()
