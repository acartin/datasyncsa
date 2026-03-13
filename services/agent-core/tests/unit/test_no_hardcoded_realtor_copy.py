from __future__ import annotations

import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.prompt_service import PromptService
from app.repositories.prompt_repository import prompt_repository


FORBIDDEN_PATTERNS = (
    "Te comparto 4 opciones",
    "habitaciones, presupuesto y banos",
    "zona indicada",
    "seleccion inicial",
    "realtor_guidance",
    "Regla realtor: usa un tono proactivo",
)


def test_synthesizer_prompt_uses_db_text_without_inline_realtor_heuristics(monkeypatch) -> None:
    async def fake_get_client_vertical_slug(client_id: str | None) -> str | None:
        return "real-estate"

    async def fake_get_lead_prompt(*, client_id: str | None, slug: str) -> str | None:
        return None

    async def fake_get_ai_system_prompt(*, node_slug: str, vertical_slug: str | None) -> str | None:
        if node_slug == "synthesizer_system" and vertical_slug == "real-estate":
            return "PROMPT_FROM_DB_REAL_ESTATE"
        return None

    monkeypatch.setattr(prompt_repository, "get_client_vertical_slug", fake_get_client_vertical_slug)
    monkeypatch.setattr(prompt_repository, "get_lead_prompt", fake_get_lead_prompt)
    monkeypatch.setattr(prompt_repository, "get_ai_system_prompt", fake_get_ai_system_prompt)

    service = PromptService()
    prompt = asyncio.run(
        service.resolve_synthesizer_prompt(
            vertical="generic",
            tenant_id="tenant-test",
            channel="web_html",
        )
    )

    assert "PROMPT_FROM_DB_REAL_ESTATE" in prompt
    for pattern in FORBIDDEN_PATTERNS:
        assert pattern not in prompt


def test_agent_core_sources_do_not_embed_forbidden_realtor_copy() -> None:
    source_files = (
        ROOT / "app/graph/nodes.py",
        ROOT / "app/core/prompt_service.py",
    )

    for source_file in source_files:
        content = source_file.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            assert pattern not in content
