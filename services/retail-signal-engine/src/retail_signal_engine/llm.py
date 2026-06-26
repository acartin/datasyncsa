"""LLM synthesis using Google Gemini with deterministic fallback."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


DEFAULT_MODEL = "gemini-2.5-flash-lite"
PROMPT_VERSION = "retail_signal_synthesis_v3_en"


def fallback_narrative(signal: dict[str, Any]) -> dict[str, str]:
    signal_type = signal["signal_type"]
    brand = signal.get("perspective_brand") or "The brand"
    chain = signal.get("chain") or "the chain"
    metrics = signal.get("metrics") or {}
    evidence = signal.get("evidence") or {}
    product = evidence.get("product") or "the monitored product"

    def money(value: Any) -> str:
        return "N/A" if value is None else f"CRC {float(value):,.0f}"

    def pct(value: Any) -> str:
        return "N/A" if value is None else f"{float(value):.1f}%"

    if signal_type == "brand_over_market":
        gap = metrics.get("gap_pct")
        return {
            "headline": f"{brand} is priced above market in {chain}.",
            "summary": f"The brand is positioned above the market reference in {chain} ({gap} points vs reference).",
            "business_reading": "The signal should be validated against SKU-level evidence before deciding whether this is premium positioning, operational misalignment, or lower promotional pressure.",
            "recommended_action": "Review the SKUs driving the gap and validate whether a tactical price or promotion adjustment is needed.",
            "tone": "warning",
        }
    if signal_type == "brand_under_market":
        return {
            "headline": f"{brand} is aggressively priced in {chain}.",
            "summary": f"The brand is positioned below the market reference in {chain}.",
            "business_reading": "This may be a deliberate competitive posture or a price alignment issue that should be monitored.",
            "recommended_action": "Defend the position and monitor competitor response.",
            "tone": "opportunity",
        }
    if signal_type == "driver_sku_detected":
        return {
            "headline": f"A small set of SKUs is driving the gap for {brand} in {chain}.",
            "summary": "The competitive gap is concentrated in a limited group of products.",
            "business_reading": "Commercial review can focus on the driver SKUs instead of the full basket.",
            "recommended_action": "Prioritize the driver SKUs before adjusting the broader portfolio.",
            "tone": "critical",
        }
    if signal_type == "promo_price_break":
        product = (signal.get("evidence") or {}).get("product") or "a monitored SKU"
        gap = metrics.get("gap_vs_market_avg_pct")
        discount = metrics.get("discount_pct")
        return {
            "headline": f"{chain} showed an aggressive promotional price on {product}.",
            "summary": f"{product} was observed with a promotional price materially below the market average ({gap}% below market average; max discount {discount}%).",
            "business_reading": "This appears to be a tactical promotional price break supported by observed store-level evidence.",
            "recommended_action": "Validate the store evidence and assess whether the promotion requires a competitive response or closer monitoring.",
            "tone": "opportunity",
        }
    if signal_type in {"regular_price_decrease", "regular_price_increase"}:
        previous_price = metrics.get("previous_value")
        current_price = metrics.get("current_value")
        change_pct = metrics.get("change_pct")
        observed_locations = metrics.get("observed_locations")
        available_locations = metrics.get("available_locations")
        direction = "decreased" if signal_type == "regular_price_decrease" else "increased"
        tone = "opportunity" if signal_type == "regular_price_decrease" else "warning"
        coverage = (
            f" across {available_locations} available stores out of {observed_locations} observed"
            if available_locations is not None and observed_locations is not None
            else ""
        )
        return {
            "headline": f"{product} {direction} in regular price at {chain}.",
            "summary": f"The observed regular price moved from {money(previous_price)} to {money(current_price)} ({pct(change_pct)}){coverage}.",
            "business_reading": "This is a store-observed regular price movement, not a promotion, and should be read against the product's competitive position in the same chain.",
            "recommended_action": "Validate the store evidence, compare against the product across chains, and decide whether the new regular price requires monitoring or a commercial response.",
            "tone": tone,
        }
    if signal_type == "sku_price_gap":
        avg_price = metrics.get("avg_price")
        best_price = metrics.get("market_best_price")
        gap_pct = metrics.get("gap_pct")
        gap_amount = metrics.get("gap_amount")
        best_chain = evidence.get("best_price_chain") or "the best observed chain"
        return {
            "headline": f"{product} is above the best observed market price in {chain}.",
            "summary": f"Average observed price is {money(avg_price)} vs {money(best_price)} in {best_chain}, a gap of {money(gap_amount)} ({pct(gap_pct)}).",
            "business_reading": "The gap is SKU-specific, so the first review should focus on this product and its store evidence before broader brand action.",
            "recommended_action": "Check the store evidence and product-across-chains view, then decide whether the gap is acceptable positioning or needs a pricing response.",
            "tone": "warning",
        }
    return {
        "headline": f"Relevant price gap detected for {brand} in {chain}.",
        "summary": "A relevant difference was detected against the best observed market price.",
        "business_reading": "The evidence suggests a specific commercial review opportunity.",
        "recommended_action": "Validate the observed price, leading chain, and affected product.",
        "tone": "warning",
    }


def synthesize_with_gemini(
    *,
    api_key: str | None,
    model: str,
    signal: dict[str, Any],
) -> dict[str, str]:
    if not api_key:
        return fallback_narrative(signal)

    prompt = {
        "role": "system",
        "instruction": (
            "You are a senior retail pricing analyst. You receive a signal that "
            "has already been calculated by deterministic code. Do not invent "
            "metrics, URLs, prices, brands, chains, stores, or products. Only "
            "write an executive reading and suggested action. The data measures "
            "observed prices, price gaps, visibility, promotions, coverage, and "
            "evidence; it does not measure sales, revenue, margin, units sold, "
            "real market share, customer behavior, or elasticity. If "
            "lifecycle_status is present, use it to distinguish new, persistent, "
            "worsened, or improved signals without exaggeration. Do not mention "
            "sales, revenue, margin, market share, elasticity, demand, or volume "
            "unless those exact facts are explicitly present in the signal. "
            "For promo_price_break signals, make the promotional price break the "
            "center of the story; do not dilute it into a generic best-price "
            "or market-alignment message. "
            "If signal.llm_guidance is present, follow it as the event-specific "
            "brief for what to emphasize and what not to infer. "
            "Respond in English and return JSON only."
        ),
        "required_json_fields": [
            "headline",
            "summary",
            "business_reading",
            "recommended_action",
            "tone",
        ],
        "tone_options": ["critical", "warning", "opportunity", "neutral"],
        "signal": signal,
    }
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Generate an executive narrative in English for this "
                            "retail intelligence signal. Return JSON only.\n\n"
                            + json.dumps(prompt, ensure_ascii=False)
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + model
        + ":generateContent?key="
        + api_key
    )
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        text = response_payload["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
    except (KeyError, json.JSONDecodeError, TimeoutError, urllib.error.URLError):
        return fallback_narrative(signal)

    fallback = fallback_narrative(signal)
    return {
        "headline": str(parsed.get("headline") or fallback["headline"]),
        "summary": str(parsed.get("summary") or fallback["summary"]),
        "business_reading": str(parsed.get("business_reading") or fallback["business_reading"]),
        "recommended_action": str(parsed.get("recommended_action") or fallback["recommended_action"]),
        "tone": str(parsed.get("tone") or fallback["tone"]),
    }
