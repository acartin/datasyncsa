"""Deterministic financial calculator for realtor flows."""

from __future__ import annotations

from typing import Any

from services.ai_runtime.domain.ports import GraphDependencies
from services.ai_runtime.domain.state import RealtorGraphState
from services.ai_runtime.graph._shared.nodes.helpers import complete_active_intent


BANK_RATES = {
    "BCR": 0.0825,
    "BN": 0.08,
    "BAC": 0.089,
    "BPDC": 0.079,
}


async def financial_calc(state: dict[str, Any], deps: GraphDependencies) -> dict[str, Any]:
    _ = deps
    graph_state = RealtorGraphState.model_validate(state)
    context = graph_state.financial_context
    if not context.price and graph_state.last_mentioned:
        context = context.model_copy(
            update={
                "property_id": graph_state.last_mentioned.id,
                "price": graph_state.last_mentioned.price,
                "currency": graph_state.last_mentioned.currency,
            }
        )

    price = float(context.price or 0)
    prima = float(context.prima or (price * 0.2))
    plazo = int(context.plazo or 30)
    banco = context.banco or "BCR"
    annual_rate = BANK_RATES.get(banco, BANK_RATES["BCR"])
    financed = max(price - prima, 0)
    monthly_rate = annual_rate / 12
    periods = max(plazo * 12, 1)
    monthly_payment = 0.0
    if financed > 0:
        monthly_payment = financed * monthly_rate / (1 - (1 + monthly_rate) ** (-periods))
    bono_sugef = max(price * 0.03, 0) if price <= 120000 else 0
    result = {
        "banco": banco,
        "tasa_anual": annual_rate,
        "monto_financiado": round(financed, 2),
        "prima": round(prima, 2),
        "plazo_anos": plazo,
        "cuota_mensual": round(monthly_payment, 2),
        "bono_sugef_estimado": round(bono_sugef, 2),
    }
    return {
        "financial_context": context.model_copy(update={"resultado": result}).model_dump(mode="json"),
        "turn_outputs": [*graph_state.turn_outputs, {"type": "financial_calc", "result": result}],
        **complete_active_intent(graph_state, {"type": "financial_calc", "result": result}),
    }
