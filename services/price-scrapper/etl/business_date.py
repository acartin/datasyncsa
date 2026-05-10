#!/usr/bin/env python3
"""Helpers para fecha de negocio diaria en America/Costa_Rica."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


CR_TIMEZONE = ZoneInfo("America/Costa_Rica")


def current_business_date_key() -> int:
    return int(datetime.now(CR_TIMEZONE).strftime("%Y%m%d"))


def business_date_key_from_iso(timestamp_text: str) -> int:
    dt = datetime.fromisoformat(timestamp_text)
    return int(dt.astimezone(CR_TIMEZONE).strftime("%Y%m%d"))


def parse_business_date_key(date_text: str | None) -> int:
    if not date_text:
        return current_business_date_key()
    parsed = datetime.strptime(date_text, "%Y-%m-%d")
    return int(parsed.strftime("%Y%m%d"))
