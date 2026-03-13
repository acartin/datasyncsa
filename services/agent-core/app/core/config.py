from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = int(os.getenv("AGENT_CORE_PORT", "8000"))
    api_prefix: str = "/api/v1"

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@postgres:5432/agentic",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    google_api_key: Optional[str] = os.getenv("GOOGLE_API_KEY")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")
    llm_timeout_secs: int = int(os.getenv("LLM_TIMEOUT_SECS", "30"))
    llm_max_output_tokens: int = int(os.getenv("CHAT_LLM_MAX_OUTPUT_TOKENS", "512"))
    synth_max_output_tokens: int = int(os.getenv("AGENT_CORE_SYNTH_MAX_OUTPUT_TOKENS", "900"))

    rag_retriever_url: str = os.getenv(
        "RAG_RETRIEVER_V2_URL",
        "http://semantic-adapter-v2:8000",
    )
    rag_retriever_search_path: str = os.getenv(
        "RAG_RETRIEVER_V2_SEARCH_PATH",
        "/api/v2/search",
    )
    rag_retriever_timeout_secs: int = int(os.getenv("RAG_RETRIEVER_V2_TIMEOUT_SECS", "10"))
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "3"))
    synth_context_max_chars: int = int(os.getenv("AGENT_CORE_SYNTH_CONTEXT_MAX_CHARS", "1800"))
    synth_string_max_chars: int = int(os.getenv("AGENT_CORE_SYNTH_STRING_MAX_CHARS", "240"))
    synth_rag_chunk_limit: int = int(os.getenv("AGENT_CORE_SYNTH_RAG_CHUNK_LIMIT", "3"))
    synth_rag_chunk_max_chars: int = int(os.getenv("AGENT_CORE_SYNTH_RAG_CHUNK_MAX_CHARS", "320"))
    synth_realtor_listing_limit: int = int(os.getenv("AGENT_CORE_SYNTH_REALTOR_LISTING_LIMIT", "4"))
    synth_realtor_features_limit: int = int(os.getenv("AGENT_CORE_SYNTH_REALTOR_FEATURES_LIMIT", "8"))
    synth_realtor_images_per_listing: int = int(os.getenv("AGENT_CORE_SYNTH_REALTOR_IMAGES_PER_LISTING", "1"))
    synth_workflow_output_items: int = int(os.getenv("AGENT_CORE_SYNTH_WORKFLOW_OUTPUT_ITEMS", "8"))
    runtime_schemas_dir: str = os.getenv(
        "AGENT_CORE_RUNTIME_SCHEMAS_DIR",
        "schemas/agent_core/runtime",
    )

    allowed_tenants_csv: str = os.getenv("AGENT_CORE_ALLOWED_TENANTS", "")
    policy_min_confidence: float = float(os.getenv("AGENT_CORE_MIN_CONFIDENCE", "0.55"))
    policy_max_tool_calls: int = int(os.getenv("AGENT_CORE_MAX_TOOL_CALLS", "2"))
    policy_allow_side_effects: bool = os.getenv("AGENT_CORE_ALLOW_SIDE_EFFECTS", "true").lower() == "true"
    realtor_property_card_limit: int = int(os.getenv("AGENT_CORE_REALTOR_CARD_LIMIT", "4"))

    scoring_enabled: bool = os.getenv("SCORING_BG_ENABLED", "true").lower() == "true"
    scoring_core_api: str = os.getenv("SCORING_CORE_API", "http://scoring-core:8000")
    scoring_api_prefix: str = os.getenv("SCORING_API_PREFIX", "/api/v1")

    agent_core_api: str = os.getenv("AGENT_CORE_API", "http://agent-core:8000")
    workflow_registry_json: str = os.getenv("WORKFLOW_REGISTRY_JSON", "{}")

    persistence_root: str = os.getenv("AGENT_CORE_PERSISTENCE_ROOT", "/tmp/agent-core")
    internal_api_token: str = os.getenv("INTERNAL_API_TOKEN", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Prompt defaults. Can be replaced by DB rows later.
    planner_system_prompt_default: str = os.getenv(
        "AGENT_CORE_PLANNER_SYSTEM_PROMPT",
        "Eres un planificador conversacional. "
        "Devuelve SOLO el objeto JSON de RouterDecision, sin markdown y sin envolturas extras. "
        "Regla de decisión: "
        "1) Usa goal='rag' cuando el usuario pida información, resumen, explicación o verificación de documentos/políticas/contenido del tenant; en ese caso incluye exactamente un tool_call rag con query_text útil y top_k. "
        "2) Usa goal='clarify' solo si falta información crítica para ejecutar la acción solicitada; siempre incluye clarify_message. "
        "3) Usa goal='answer' únicamente si la respuesta no requiere tools. "
        "No inventes tools ni campos fuera del contrato.",
    )
    synthesizer_system_prompt_default: str = os.getenv(
        "AGENT_CORE_SYNTH_SYSTEM_PROMPT",
        "Eres un redactor experto. "
        "Responde SOLO JSON estricto con text, evidence_ids y needs_cards. "
        "needs_cards debe ser booleano true/false, nunca lista. "
        "Si hay tool_results, cita evidencia real en evidence_ids (chunk_id/listing_id válidos).",
    )

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    @property
    def workflow_registry(self) -> Dict[str, Dict[str, Any]]:
        if not self.workflow_registry_json:
            return {}
        try:
            payload = json.loads(self.workflow_registry_json)
            if isinstance(payload, dict):
                return payload
        except Exception:
            return {}
        return {}

    @property
    def allowed_tenants(self) -> set[str]:
        tenants = set()
        for raw in [t.strip() for t in self.allowed_tenants_csv.split(",") if t.strip()]:
            tenants.add(raw)
        return tenants

    @property
    def runtime_trace_path(self) -> str:
        path = Path(self.persistence_root) / "trace"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)


settings = Settings()
