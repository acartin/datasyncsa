"""
Matriz de Pruebas para Chat Multi-Canal

Define los casos de prueba por canal x vertical.
"""

from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum


class Channel(str, Enum):
    WEB_HTML = "web_html"
    META_WHATSAPP = "meta_whatsapp"
    META_IG = "meta_ig"
    API = "api"


class Vertical(str, Enum):
    REALTOR = "realtor"
    GENERIC = "generic"


@dataclass
class TestCase:
    """Representa un caso de prueba."""
    channel: str
    vertical: str
    test_type: str
    description: str
    expected_components: List[str]
    expected_format: str


TEST_MATRIX: List[TestCase] = [
    # Web HTML + Realtor
    TestCase(
        channel=Channel.WEB_HTML,
        vertical=Vertical.REALTOR,
        test_type="happy_path",
        description="Chat web con respuesta de propiedad",
        expected_components=["chat_text", "property_card"],
        expected_format="sdui",
    ),
    TestCase(
        channel=Channel.WEB_HTML,
        vertical=Vertical.REALTOR,
        test_type="gallery",
        description="Chat web con galería de imágenes",
        expected_components=["chat_text", "gallery"],
        expected_format="sdui",
    ),
    TestCase(
        channel=Channel.WEB_HTML,
        vertical=Vertical.REALTOR,
        test_type="map",
        description="Chat web con ubicación",
        expected_components=["chat_text", "map"],
        expected_format="sdui",
    ),
    
    # Web HTML + Generic
    TestCase(
        channel=Channel.WEB_HTML,
        vertical=Vertical.GENERIC,
        test_type="happy_path",
        description="Chat web genérico",
        expected_components=["chat_text"],
        expected_format="sdui",
    ),
    TestCase(
        channel=Channel.WEB_HTML,
        vertical=Vertical.GENERIC,
        test_type="blocked_property_card",
        description="Generic debe bloquear property_card",
        expected_components=["chat_text"],
        expected_format="sdui",
    ),
    
    # Meta WhatsApp + Realtor
    TestCase(
        channel=Channel.META_WHATSAPP,
        vertical=Vertical.REALTOR,
        test_type="text",
        description="WhatsApp con texto simple",
        expected_components=["chat_text"],
        expected_format="meta_message",
    ),
    TestCase(
        channel=Channel.META_WHATSAPP,
        vertical=Vertical.REALTOR,
        test_type="image",
        description="WhatsApp con imagen",
        expected_components=["chat_text", "image"],
        expected_format="meta_message",
    ),
    TestCase(
        channel=Channel.META_WHATSAPP,
        vertical=Vertical.REALTOR,
        test_type="list",
        description="WhatsApp con lista de opciones",
        expected_components=["chat_text", "list"],
        expected_format="meta_message",
    ),
    TestCase(
        channel=Channel.META_WHATSAPP,
        vertical=Vertical.REALTOR,
        test_type="property_card_degraded",
        description="WhatsApp degrada property_card a texto",
        expected_components=["chat_text"],
        expected_format="meta_message",
    ),
    
    # Meta WhatsApp + Generic
    TestCase(
        channel=Channel.META_WHATSAPP,
        vertical=Vertical.GENERIC,
        test_type="quick_replies",
        description="WhatsApp con quick replies",
        expected_components=["chat_text", "quick_replies"],
        expected_format="meta_message",
    ),
    
    # Meta Instagram + Realtor
    TestCase(
        channel=Channel.META_IG,
        vertical=Vertical.REALTOR,
        test_type="image",
        description="Instagram con imagen",
        expected_components=["chat_text", "image"],
        expected_format="meta_message",
    ),
    
    # Meta Instagram + Generic
    TestCase(
        channel=Channel.META_IG,
        vertical=Vertical.GENERIC,
        test_type="quick_replies",
        description="Instagram con quick replies",
        expected_components=["chat_text", "quick_replies"],
        expected_format="meta_message",
    ),
    
    # API + Realtor
    TestCase(
        channel=Channel.API,
        vertical=Vertical.REALTOR,
        test_type="json_contract",
        description="API con respuesta JSON estructurada",
        expected_components=["chat_text", "property_card"],
        expected_format="json_contract",
    ),
    TestCase(
        channel=Channel.API,
        vertical=Vertical.REALTOR,
        test_type="gallery",
        description="API con galería",
        expected_components=["chat_text", "gallery"],
        expected_format="json_contract",
    ),
    
    # API + Generic
    TestCase(
        channel=Channel.API,
        vertical=Vertical.GENERIC,
        test_type="json_contract",
        description="API genérica",
        expected_components=["chat_text"],
        expected_format="json_contract",
    ),
]


def get_tests_for_channel(channel: str) -> List[TestCase]:
    """Obtiene todos los tests para un canal específico."""
    return [t for t in TEST_MATRIX if t.channel == channel]


def get_tests_for_vertical(vertical: str) -> List[TestCase]:
    """Obtiene todos los tests para un vertical específico."""
    return [t for t in TEST_MATRIX if t.vertical == vertical]


def get_test_matrix_summary() -> Dict[str, Any]:
    """Resumen de la matriz de pruebas."""
    channels = set(t.channel for t in TEST_MATRIX)
    verticals = set(t.vertical for t in TEST_MATRIX)
    
    return {
        "total_tests": len(TEST_MATRIX),
        "channels": list(channels),
        "verticals": list(verticals),
        "tests_by_channel": {
            ch: len(get_tests_for_channel(ch))
            for ch in channels
        },
        "tests_by_vertical": {
            v: len(get_tests_for_vertical(v))
            for v in verticals
        },
    }
