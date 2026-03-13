from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def load_canonical_property_contract() -> dict[str, Any]:
    path = _resolve_contract_path()
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("invalid canonical_property contract payload")
    return payload


@lru_cache(maxsize=1)
def canonical_feature_keys() -> dict[str, str]:
    contract = load_canonical_property_contract()
    fields = contract.get("fields") or {}
    if not isinstance(fields, dict):
        raise ValueError("canonical_property.fields is invalid")
    features = fields.get("features") or {}
    if not isinstance(features, dict):
        raise ValueError("canonical_property.fields.features is invalid")

    required = (
        "address",
        "amenities",
        "bedrooms_clean",
        "bathrooms_clean",
        "garage_clean",
        "sqm_clean",
    )
    missing = [name for name in required if name not in features]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"canonical_property missing feature keys: {joined}")
    return {name: name for name in required}


def _resolve_contract_path() -> Path:
    for path in _candidate_paths():
        if path.exists() and path.is_file():
            return path
    tried = ", ".join(str(path) for path in _candidate_paths())
    raise FileNotFoundError(f"canonical_property.json not found. tried: {tried}")


def _candidate_paths() -> list[Path]:
    current = Path(__file__).resolve()
    candidates = [
        Path("schemas/canonical_property.json"),
        Path.cwd() / "schemas/canonical_property.json",
        Path("/app/schemas/canonical_property.json"),
    ]
    for parent in current.parents:
        candidates.append(parent / "schemas/canonical_property.json")
    return candidates
