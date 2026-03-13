from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.models.contracts import GoalType, ToolName


class PolicyDefaults(BaseModel):
    min_confidence: float = Field(ge=0.0, le=1.0)
    max_tool_calls: int = Field(ge=0)
    allow_side_effects: bool = True


class PolicyVerticalConfig(BaseModel):
    allowed_goals: set[GoalType] = Field(default_factory=set)
    allowed_tools: set[ToolName] = Field(default_factory=set)


class PolicyGateRuntimeConfig(BaseModel):
    contract: str
    version: str
    defaults: PolicyDefaults
    verticals: dict[str, PolicyVerticalConfig]
    required_tools_by_goal: dict[GoalType, set[ToolName]] = Field(default_factory=dict)


class ToolSpecConfig(BaseModel):
    input_contract: str
    output_contract: str
    deterministic_runtime: bool = True
    free_sql_allowed: bool = False
    translator: str | None = None


class ToolVerticalConfig(BaseModel):
    enabled_tools: set[ToolName] = Field(default_factory=set)


class ToolRegistryRuntimeConfig(BaseModel):
    contract: str
    version: str
    tool_specs: dict[ToolName, ToolSpecConfig]
    verticals: dict[str, ToolVerticalConfig]


class CardTemplateConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_path: str = Field(alias="schema")
    source: str


class CardVerticalConfig(BaseModel):
    allowed_cards: set[str] = Field(default_factory=set)


class CardRegistryRuntimeConfig(BaseModel):
    contract: str
    version: str
    cards: dict[str, CardTemplateConfig]
    verticals: dict[str, CardVerticalConfig]
    rules: list[str] = Field(default_factory=list)


class RuntimeRegistryBundle(BaseModel):
    policy_gate: PolicyGateRuntimeConfig
    tool_registry: ToolRegistryRuntimeConfig
    card_registry: CardRegistryRuntimeConfig


def _candidate_runtime_dirs() -> list[Path]:
    candidates: list[Path] = []

    configured = Path(settings.runtime_schemas_dir)
    candidates.append(configured)

    if not configured.is_absolute():
        candidates.append(Path.cwd() / configured)

    current = Path(__file__).resolve()
    for parent in current.parents:
        candidates.append(parent / "schemas/agent_core/runtime")

    # container default for compose runtime
    candidates.append(Path("/app/schemas/agent_core/runtime"))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _resolve_runtime_dir() -> Path:
    for candidate in _candidate_runtime_dirs():
        if candidate.exists() and candidate.is_dir():
            return candidate
    all_candidates = ", ".join(str(path) for path in _candidate_runtime_dirs())
    raise FileNotFoundError(f"runtime schemas directory not found. tried: {all_candidates}")


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid runtime schema payload in {path}")
    return payload


@lru_cache(maxsize=1)
def load_runtime_registry() -> RuntimeRegistryBundle:
    base = _resolve_runtime_dir()
    policy_payload = _read_json(base / "policy_gate.v1.json")
    tools_payload = _read_json(base / "tool_registry.v1.json")
    cards_payload = _read_json(base / "card_registry.v1.json")
    return RuntimeRegistryBundle(
        policy_gate=PolicyGateRuntimeConfig.model_validate(policy_payload),
        tool_registry=ToolRegistryRuntimeConfig.model_validate(tools_payload),
        card_registry=CardRegistryRuntimeConfig.model_validate(cards_payload),
    )


def get_policy_gate_config() -> PolicyGateRuntimeConfig:
    return load_runtime_registry().policy_gate


def get_tool_registry_config() -> ToolRegistryRuntimeConfig:
    return load_runtime_registry().tool_registry


def get_card_registry_config() -> CardRegistryRuntimeConfig:
    return load_runtime_registry().card_registry
