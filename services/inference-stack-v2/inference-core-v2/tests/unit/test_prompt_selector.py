import pytest

from app.services.prompt_selector import (
    PromptSelector,
    ChatPromptTemplate,
    DEFAULT_PROMPT_SLUGS,
    prompt_selector,
)


class TestPromptSelector:
    def setup_method(self):
        self.selector = PromptSelector()
        self.selector.clear_cache()

    def test_realtor_web_html_prompt(self):
        slug = self.selector.get_prompt_slug("realtor", "web_html")
        assert slug == "realtor_web_v1"

    def test_realtor_meta_whatsapp_prompt(self):
        slug = self.selector.get_prompt_slug("realtor", "meta_whatsapp")
        assert slug == "realtor_meta_whatsapp_v1"

    def test_realtor_meta_ig_prompt(self):
        slug = self.selector.get_prompt_slug("realtor", "meta_ig")
        assert slug == "realtor_meta_ig_v1"

    def test_realtor_api_prompt(self):
        slug = self.selector.get_prompt_slug("realtor", "api")
        assert slug == "realtor_api_v1"

    def test_generic_web_html_prompt(self):
        slug = self.selector.get_prompt_slug("generic", "web_html")
        assert slug == "generic_web_v1"

    def test_generic_api_prompt(self):
        slug = self.selector.get_prompt_slug("generic", "api")
        assert slug == "generic_api_v1"

    def test_unknown_vertical_fallback_to_generic(self):
        slug = self.selector.get_prompt_slug("unknown_vertical", "web_html")
        assert slug == "generic_web_v1"

    def test_real_estate_alias_maps_to_realtor(self):
        slug = self.selector.get_prompt_slug("real-estate", "web_html")
        assert slug == "realtor_web_v1"

    def test_unknown_channel_fallback_to_api(self):
        slug = self.selector.get_prompt_slug("realtor", "unknown_channel")
        assert slug == "realtor_api_v1"

    def test_cache_is_used(self):
        slug1 = self.selector.get_prompt_slug("realtor", "web_html")
        slug2 = self.selector.get_prompt_slug("realtor", "web_html")
        assert slug1 == slug2

    def test_clear_cache(self):
        self.selector.get_prompt_slug("realtor", "web_html")
        self.selector.clear_cache()
        assert len(self.selector._cache) == 0

    def test_all_default_slugs_defined(self):
        assert len(DEFAULT_PROMPT_SLUGS) == 8
        for (vertical, channel), slug in DEFAULT_PROMPT_SLUGS.items():
            assert vertical in ["realtor", "generic"]
            assert channel in ["web_html", "meta_whatsapp", "meta_ig", "api"]
            assert slug.endswith("_v1")


class TestChatPromptTemplate:
    def test_realtor_web_html_template(self):
        template = ChatPromptTemplate.get_system_prompt_template("realtor", "web_html")
        assert "bienes raíces" in template or "real estate" in template.lower()
        assert "property_search" in template
        assert "web_html" in template.lower() or "html" in template.lower()

    def test_generic_api_template(self):
        template = ChatPromptTemplate.get_system_prompt_template("generic", "api")
        assert "atención general" in template or "general" in template.lower()
        assert "API" in template or "JSON" in template

    def test_intent_extraction_prompt(self):
        prompt = ChatPromptTemplate.get_intent_extraction_prompt(
            "Quiero ver casas en Escazu",
            {"channel": "web_html", "vertical": "realtor"}
        )
        assert "Quiero ver casas en Escazu" in prompt
        assert "web_html" in prompt
        assert "realtor" in prompt
        assert "PRIMARY_INTENT" in prompt
        assert "ENTITIES" in prompt

    def test_intent_extraction_without_context(self):
        prompt = ChatPromptTemplate.get_intent_extraction_prompt("Hola")
        assert "Hola" in prompt
        assert "PRIMARY_INTENT" in prompt


class TestPromptSelectorSingleton:
    def test_singleton_exists(self):
        assert prompt_selector is not None
        assert isinstance(prompt_selector, PromptSelector)

    def test_singleton_returns_correct_slugs(self):
        assert prompt_selector.get_prompt_slug("realtor", "api") == "realtor_api_v1"
        assert prompt_selector.get_prompt_slug("generic", "web_html") == "generic_web_v1"


class TestSeparationOfConcerns:
    """
    Tests verifying the separation between prompt (semantics) and policy (render).
    """

    def test_prompt_defines_semantics_not_ui(self):
        template = ChatPromptTemplate.get_system_prompt_template("realtor", "web_html")
        assert "property_card" not in template.lower()
        assert "gallery" not in template.lower()
        assert "inten" in template.lower()

    def test_prompt_channel_affects_style_not_components(self):
        web_template = ChatPromptTemplate.get_system_prompt_template("realtor", "web_html")
        whatsapp_template = ChatPromptTemplate.get_system_prompt_template("realtor", "meta_whatsapp")
        
        assert web_template != whatsapp_template
        assert "UI" in web_template or "componentes" in web_template
        assert "WhatsApp" in whatsapp_template or "limitado" in whatsapp_template

    def test_vertical_affects_domain_not_render(self):
        realtor_template = ChatPromptTemplate.get_system_prompt_template("realtor", "api")
        generic_template = ChatPromptTemplate.get_system_prompt_template("generic", "api")
        
        assert realtor_template != generic_template
        assert "propiedad" in realtor_template or "property" in realtor_template.lower()
        assert "soporte" in generic_template or "support" in generic_template.lower()
