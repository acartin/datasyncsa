import pytest

from app.transformer import core as transformer_core
from app.transformer.core import SDUITransformer


@pytest.mark.asyncio
async def test_transform_init_has_no_fallback_message(monkeypatch):
    monkeypatch.setattr(transformer_core.db_manager, "get_branding", lambda client_id, brand_project=None: None)
    transformer = SDUITransformer()

    response = await transformer.transform(
        {"answer": "", "sources": []},
        session_id="init",
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
        include_fallback_text=False,
    )

    assert response.session_id == "init"
    assert response.components == []
    assert response.branding is not None


@pytest.mark.asyncio
async def test_transform_builds_property_card_from_sources(monkeypatch):
    def fake_branding(_client_id, _brand_project=None):
        return None

    def fake_property(_prop_id):
        return {
            "id": "p-1",
            "title": "Casa Premium",
            "price": 350000,
            "address_city": "Escazu",
            "address_state": "San Jose",
            "images": ["https://example.com/house.jpg"],
            "features": {"highlights": ["3 cuartos"]},
        }

    monkeypatch.setattr(transformer_core.db_manager, "get_branding", fake_branding)
    monkeypatch.setattr(transformer_core.db_manager, "get_property", fake_property)

    transformer = SDUITransformer()
    response = await transformer.transform(
        {
            "answer": "Tengo una opcion para vos.",
            "sources": [{"metadata": {"id": "p-1"}}],
        },
        session_id="abc",
        client_id="64f357a0-98eb-44f1-9f41-6e615ed26180",
    )

    component_types = [comp.type for comp in response.components]
    assert "chat" in component_types
    assert "property-card" in component_types
