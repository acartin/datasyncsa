"""
Scoring Engine with Gemini LLM Integration

Implements real scoring using Gemini LLM with dynamic prompts from database.
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional
from uuid import UUID

from app.core.config import settings
from app.services.prompt_builder import PromptBuilder

logger = logging.getLogger("inference-core-v2.scoring_engine")

DEFAULT_EXTRACTION_FIELDS = [
    {"key": "extracted_name", "type": "string"},
    {"key": "extracted_email", "type": "string"},
    {"key": "extracted_phone", "type": "string"},
    {"key": "extracted_appointment_type", "type": "string"},
    {"key": "extracted_insurance", "type": "string"},
    {"key": "extracted_budget", "type": "string"},
    {"key": "extracted_symptoms", "type": "string"},
    {"key": "extracted_preferred_date", "type": "string"},
    {"key": "extracted_preference", "type": "string"},
    {"key": "extracted_payment_preference", "type": "string"},
]


class ScoringEngine:
    """
    Scoring engine that uses Gemini LLM for lead analysis.
    
    Features:
    - Dynamic prompts from database configuration
    - Structured JSON output
    - Retry logic with exponential backoff
    - Timeout handling
    """
    
    def __init__(self):
        self._client = None
        self._model_id = settings.llm_model
        self._temperature = settings.llm_temperature
        self._max_retries = settings.llm_max_retries
        self._timeout = settings.llm_timeout_secs
    
    @property
    def client(self):
        """Lazy initialization of Gemini client"""
        if self._client is None:
            if not settings.google_api_key:
                raise ValueError("GOOGLE_API_KEY not configured")
            
            try:
                from google import genai
                self._client = genai.Client(api_key=settings.google_api_key)
            except ImportError:
                raise ImportError("google-genai package not installed. Run: pip install google-genai")
        
        return self._client
    
    async def analyze_conversation(
        self,
        conversation_text: str,
        model_config: Dict[str, Any],
        prompt_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze a conversation and return scoring results.
        
        Args:
            conversation_text: Full conversation text to analyze
            model_config: Model configuration with criteria and bands
            prompt_config: Prompt configuration with template and extraction_schema
        
        Returns:
            Dict with:
            - scores: Dict[criterion_key, score]
            - explanations: Dict[criterion_key, explanation]
            - extraction_result: Dict with extracted data
            - reasoning: str
            - prompt_snapshot: str (the actual prompt used)
        """
        vertical_name = model_config.get("vertical_name", "leads")
        vertical_slug = model_config.get("vertical_slug", "")
        criteria = model_config.get("criteria", [])
        bands = self._extract_bands_from_criteria(criteria)
        
        prompt_template = prompt_config.get("prompt_template")
        if not prompt_template:
            raise ValueError("No prompt_template found in prompt_config - prompt must be configured in database")
        
        builder = PromptBuilder(custom_template=prompt_template)
        
        extraction_fields = self._merge_extraction_fields(
            builder.get_extraction_fields_from_prompt(),
            DEFAULT_EXTRACTION_FIELDS,
        )
        
        system_prompt = builder.build_prompt(
            vertical_name=vertical_name,
            criteria=criteria,
            bands=bands,
            extraction_fields=extraction_fields,
            business_domain=model_config.get("business_domain"),
            lead_type=model_config.get("lead_type"),
            locale=model_config.get("locale"),
            timestamp_utc=model_config.get("timestamp_utc")
        )
        
        response_schema = builder.build_response_schema(criteria, extraction_fields)
        
        result = await self._call_gemini(
            system_prompt=system_prompt,
            conversation_text=conversation_text,
            response_schema=response_schema
        )
        
        scores = {}
        explanations = {}
        extraction_result = {}
        confidence = None
        
        scores_container = result.get("scores", {})
        extracted_data_container = result.get("extracted_data", {})
        
        for criterion in criteria:
            key = criterion.get("criterion_key")
            if key and key in scores_container:
                scores[key] = float(scores_container[key])
                explanations[key] = result.get(f"{key}_explanation", "")
        
        for field in extraction_fields:
            key = field.get("key")
            if not key or key not in extracted_data_container:
                continue
            value = extracted_data_container[key]
            if self._is_meaningful_value(value):
                extraction_result[key] = value
        
        if "confidence" in result and result["confidence"] is not None:
            confidence = float(result["confidence"])
        
        return {
            "scores": scores,
            "explanations": explanations,
            "extraction_result": extraction_result,
            "reasoning": result.get("reasoning", ""),
            "confidence": confidence,
            "prompt_snapshot": system_prompt
        }

    @staticmethod
    def _is_meaningful_value(value: Any) -> bool:
        """Ignore empty/placeholder values to avoid wiping accumulated extraction."""
        if value is None:
            return False
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return False
            if normalized.lower() in {"null", "none", "n/a", "na", "unknown", "desconocido"}:
                return False
            return True
        return True
    
    async def _call_gemini(
        self,
        system_prompt: str,
        conversation_text: str,
        response_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call Gemini API with retries and timeout handling.
        
        Args:
            system_prompt: System instruction for the LLM
            conversation_text: The conversation to analyze
            response_schema: JSON schema for structured output
        
        Returns:
            Parsed JSON response from the LLM
        """
        last_error = None
        
        for attempt in range(1, self._max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self._call_gemini_internal(system_prompt, conversation_text, response_schema),
                    timeout=self._timeout
                )
                return result
            
            except asyncio.TimeoutError:
                logger.warning(f"Gemini API timeout on attempt {attempt}/{self._max_retries}")
                last_error = TimeoutError(f"LLM request timed out after {self._timeout}s")
            
            except Exception as e:
                logger.warning(f"Gemini API error on attempt {attempt}/{self._max_retries}: {e}")
                last_error = e
            
            if attempt < self._max_retries:
                delay = min(2 ** attempt, 10)
                await asyncio.sleep(delay)
        
        logger.error(f"All Gemini API attempts failed: {last_error}")
        raise last_error or Exception("Unknown error in Gemini API")
    
    async def _call_gemini_internal(
        self,
        system_prompt: str,
        conversation_text: str,
        response_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Internal method to call Gemini API.
        
        Uses structured output with JSON schema for reliable parsing.
        """
        try:
            from google.genai import types
        except ImportError:
            raise ImportError("google-genai package not installed")
        
        prompt = f"Analiza la siguiente conversación y devuelve el scoring e información extraída:\n\n{conversation_text}"
        
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self._model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self._temperature,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )
        
        try:
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.debug(f"Raw response: {response.text[:1000]}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")
    
    def _extract_bands_from_criteria(self, criteria: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract bands list from criteria (bands are nested in criteria)"""
        all_bands = []
        for criterion in criteria:
            bands = criterion.get("bands", [])
            for band in bands:
                band["criterion_id"] = criterion.get("id")
            all_bands.extend(bands)
        return all_bands

    @staticmethod
    def _merge_extraction_fields(
        prompt_fields: Optional[List[Dict[str, Any]]],
        default_fields: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Merge prompt-defined and default extraction fields without duplicates."""
        merged: List[Dict[str, Any]] = []
        seen = set()

        for field in (prompt_fields or []):
            key = field.get("key")
            if not key or key in seen:
                continue
            merged.append(field)
            seen.add(key)

        for field in (default_fields or []):
            key = field.get("key")
            if not key or key in seen:
                continue
            merged.append(field)
            seen.add(key)

        return merged
    
    def _get_extraction_fields(
        self,
        prompt_config: Dict[str, Any],
        model_config: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Get extraction fields - now defined in DB prompt, return empty for backward compatibility"""
        return None


scoring_engine = ScoringEngine()
