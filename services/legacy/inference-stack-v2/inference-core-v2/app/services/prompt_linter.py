import re
from typing import Any, Dict, List


_PLACEHOLDER_PATTERN = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")


class PromptLinter:
    """
    Validates scoring prompt templates before runtime/activation.
    """

    ALLOWED_PLACEHOLDERS = {
        "vertical_name",
        "criteria_text",
        "extraction_text",
        "business_domain",
        "locale",
        "timestamp_utc",
    }

    LEGACY_REPLACEMENTS = {
        "{conversation_text}": "",
        "{lead_type}": "{vertical_name}",
    }

    @staticmethod
    def normalize_template(template: str) -> str:
        text = template or ""
        # DB rows often contain literal "\n"; convert to real line breaks for runtime.
        text = text.replace("\\r\\n", "\n").replace("\\n", "\n")
        return text.strip()

    def lint_template(self, template: str) -> Dict[str, Any]:
        normalized = self.normalize_template(template)
        errors: List[str] = []
        warnings: List[str] = []

        if not normalized:
            errors.append("Prompt template cannot be empty.")
            return {
                "normalized_template": normalized,
                "errors": errors,
                "warnings": warnings,
                "placeholders": [],
            }

        if len(normalized) < 80:
            errors.append("Prompt template is too short (minimum 80 chars).")
        elif len(normalized) > 32000:
            errors.append("Prompt template is too long (maximum 32000 chars).")

        for legacy_token, replacement in self.LEGACY_REPLACEMENTS.items():
            if legacy_token in normalized:
                normalized = normalized.replace(legacy_token, replacement)
                warnings.append(
                    f"Legacy placeholder {legacy_token} was normalized at runtime."
                )

        placeholders = sorted(set(_PLACEHOLDER_PATTERN.findall(normalized)))
        unsupported = [p for p in placeholders if p not in self.ALLOWED_PLACEHOLDERS]
        if unsupported:
            errors.append(
                "Unsupported placeholders: " + ", ".join(unsupported)
            )

        if "{criteria_text}" not in normalized:
            warnings.append("Missing {criteria_text} placeholder; scoring criteria may be under-specified.")
        if "{vertical_name}" not in normalized:
            warnings.append("Missing {vertical_name} placeholder; vertical context may be weak.")
        if "\\n" in (template or ""):
            warnings.append("Prompt had literal \\n and was normalized to real newlines.")

        return {
            "normalized_template": normalized,
            "errors": errors,
            "warnings": warnings,
            "placeholders": placeholders,
        }

    def validate_template(self, template: str) -> Dict[str, Any]:
        result = self.lint_template(template)
        if result["errors"]:
            raise ValueError(" | ".join(result["errors"]))
        return result
