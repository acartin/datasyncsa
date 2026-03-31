import pytest

from app.services.prompt_linter import PromptLinter


def test_prompt_linter_rejects_unsupported_placeholder():
    linter = PromptLinter()
    with pytest.raises(ValueError):
        linter.validate_template(
            "Evalua leads del vertical {vertical_name} usando {criteria_text} y placeholder invalido {foo_bar}."
        )


def test_prompt_linter_normalizes_legacy_conversation_placeholder():
    linter = PromptLinter()
    result = linter.validate_template(
        "Evalua leads para {vertical_name}. Criterios:\n{criteria_text}\nConversacion:\n{conversation_text}\n"
        "Responde JSON estricto con scores y extracted_data."
    )
    assert "{conversation_text}" not in result["normalized_template"]
    assert any("Legacy placeholder {conversation_text}" in warning for warning in result["warnings"])


def test_prompt_linter_normalizes_literal_newlines():
    linter = PromptLinter()
    result = linter.validate_template(
        "Contexto de scoring para leads\\nVertical: {vertical_name}\\nCriterios:\\n{criteria_text}"
        "\\nSalida JSON estricta con campos score_total, priority_label y score_items."
    )
    assert "\\n" not in result["normalized_template"]
    assert "\n" in result["normalized_template"]


def test_prompt_linter_accepts_supported_placeholders():
    linter = PromptLinter()
    result = linter.validate_template(
        "Vertical: {vertical_name}\nCriterios:\n{criteria_text}\nExtrae: {extraction_text}\n"
        "Dominio: {business_domain}\nLocale: {locale}\nFecha: {timestamp_utc}\n"
        "Devuelve JSON estricto."
    )
    assert result["errors"] == []
