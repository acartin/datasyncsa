import unittest

from services.ai_runtime.domain.contracts import (
    ScoringFieldConfig,
    ScoringProfile,
    TenantBusinessProfile,
    TenantConfig,
)
from services.ai_runtime.domain.state import build_base_state, build_lead_advisor_state
from services.ai_runtime.graph._shared.nodes.lead_advisor_node import _select_field_to_ask
from services.ai_runtime.graph.realtor.state.model import RealtorGraphState


def _scoring_contract() -> dict:
    return {
        "progressive_profile": {
            "journey_source": "search_filters.operacion",
            "journey_field_orders": {
                "sale": [
                    "presupuesto",
                    "aprobacion",
                    "fecha_preferida",
                    "appointment_intent",
                    "tipo_cita",
                    "contacto",
                    "email",
                    "telefono",
                    "preferencias",
                    "nombre",
                ],
                "rent": [
                    "fecha_preferida",
                    "presupuesto",
                    "appointment_intent",
                    "tipo_cita",
                    "contacto",
                    "email",
                    "telefono",
                    "preferencias",
                    "nombre",
                ],
            },
            "contact_policy": {
                "default": "channel_aware",
                "by_channel": {
                    "whatsapp": "phone_first",
                    "webchat": "email_first",
                },
            },
        }
    }


def _tenant_config() -> TenantConfig:
    fields = [
        ScoringFieldConfig(key="nombre", required=True),
        ScoringFieldConfig(key="presupuesto", required=True),
        ScoringFieldConfig(key="aprobacion", required=True),
        ScoringFieldConfig(key="fecha_preferida", required=True),
        ScoringFieldConfig(key="appointment_intent", required=True),
        ScoringFieldConfig(key="tipo_cita", required=True),
        ScoringFieldConfig(key="email", required=True),
        ScoringFieldConfig(key="telefono", required=True),
    ]
    profile = ScoringProfile(
        prompt_template="prompt activo",
        extraction_fields=fields,
        scoring_contract=_scoring_contract(),
    )
    return TenantConfig(
        client_id="tenant-1",
        vertical="realtor",
        business=TenantBusinessProfile(name="Datasyncsa AI"),
        scoring_profile=profile,
    )


def _state(*, channel: str, operacion: str | None) -> tuple[RealtorGraphState, object]:
    tenant_config = _tenant_config()
    base_state = build_base_state(
        session_id="session-1",
        conversation_id="conversation-1",
        user_id="user-1",
        client_id="tenant-1",
        vertical="realtor",
        flow="realtor_flow",
        tenant_config=tenant_config,
        initial_message="hola",
        initial_message_metadata={"channel": channel},
    )
    state = RealtorGraphState.model_validate(base_state.model_dump(mode="json"))
    state.search_filters.operacion = operacion
    advisor_state = build_lead_advisor_state(tenant_config, state.lead_advisor).model_copy(
        update={"capture_exposure_count": 3}
    )
    return state, advisor_state


class RealtorProgressiveProfileTests(unittest.TestCase):
    def test_rent_journey_prioritizes_preferred_date(self) -> None:
        state, advisor_state = _state(channel="web_html", operacion="alquiler")

        field = _select_field_to_ask(
            state,
            advisor_state,
            suggested_field=None,
            dialogue_act="new_search",
            capture_exposure_count=3,
            current_turn_is_exposure=False,
        )

        self.assertEqual(field, "fecha_preferida")

    def test_sale_journey_prioritizes_budget(self) -> None:
        state, advisor_state = _state(channel="web_html", operacion="venta")

        field = _select_field_to_ask(
            state,
            advisor_state,
            suggested_field=None,
            dialogue_act="new_search",
            capture_exposure_count=3,
            current_turn_is_exposure=False,
        )

        self.assertEqual(field, "presupuesto")

    def test_contact_policy_prefers_phone_on_whatsapp(self) -> None:
        state, advisor_state = _state(channel="meta_whatsapp", operacion="venta")
        advisor_state = advisor_state.model_copy(
            update={
                "required_fields": ["email", "telefono"],
                "target_fields": ["email", "telefono"],
                "completed_fields": [],
            }
        )

        field = _select_field_to_ask(
            state,
            advisor_state,
            suggested_field="contacto",
            dialogue_act="schedule",
            capture_exposure_count=3,
            current_turn_is_exposure=False,
        )

        self.assertEqual(field, "telefono")

    def test_contact_policy_prefers_email_on_webchat(self) -> None:
        state, advisor_state = _state(channel="web_html", operacion="venta")
        advisor_state = advisor_state.model_copy(
            update={
                "required_fields": ["email", "telefono"],
                "target_fields": ["email", "telefono"],
                "completed_fields": [],
            }
        )

        field = _select_field_to_ask(
            state,
            advisor_state,
            suggested_field="contacto",
            dialogue_act="schedule",
            capture_exposure_count=3,
            current_turn_is_exposure=False,
        )

        self.assertEqual(field, "email")


if __name__ == "__main__":
    unittest.main()
