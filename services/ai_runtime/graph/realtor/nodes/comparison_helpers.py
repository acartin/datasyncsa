"""Helpers shared by realtor comparison and recommendation nodes."""

from __future__ import annotations

from services.ai_runtime.graph.realtor.contracts import Property, PropertyComparisonScore


def score_property(property_item: Property) -> PropertyComparisonScore:
    dimensions = {
        "bedrooms": float(property_item.features.bedrooms_clean),
        "bathrooms": float(property_item.features.bathrooms_clean),
        "garage": float(property_item.features.garage_clean),
        "size": float(property_item.features.sqm_clean or 0) / 25.0,
        "price_efficiency": max(0.0, 12.0 - (property_item.price / 50000.0)),
    }
    return PropertyComparisonScore(
        property_id=property_item.id,
        score_total=round(sum(dimensions.values()), 2),
        dimensions=dimensions,
    )
