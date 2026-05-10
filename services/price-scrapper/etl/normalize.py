#!/usr/bin/env python3
"""Normalizaciones compartidas para ETL y scrapers."""

from __future__ import annotations

from typing import Any


def normalize_ean(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        for entry in value:
            normalized = normalize_ean(entry)
            if normalized:
                return normalized
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit() and len(text) in (11, 12):
        return text.zfill(13)
    return text

