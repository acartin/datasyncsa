"""
Prompt Builder for Dynamic Scoring

Builds prompts dynamically from database configuration (criteria, bands, extraction schema).
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("inference-core-v2.prompt_builder")


class PromptBuilder:
    """Builds dynamic prompts for scoring based on model configuration"""
    
    def __init__(self, custom_template: str):
        self.system_template = custom_template
    
    def build_prompt(
        self,
        vertical_name: str,
        criteria: List[Dict[str, Any]],
        bands: List[Dict[str, Any]],
        extraction_fields: Optional[List[Dict[str, Any]]] = None,
        business_domain: Optional[str] = None,
        lead_type: Optional[str] = None,
        locale: Optional[str] = None,
        timestamp_utc: Optional[str] = None
    ) -> str:
        """
        Build the complete system prompt for scoring.
        
        Args:
            vertical_name: Name of the vertical (e.g., "Healthcare", "Real Estate")
            criteria: List of criteria from lead_scoring_criteria
            bands: List of bands from lead_scoring_bands (grouped by criterion)
            extraction_fields: Optional list of fields to extract from extraction_schema
            business_domain: Optional business domain for context
            lead_type: Optional lead type
            locale: Optional locale
            timestamp_utc: Optional timestamp
        
        Returns:
            Complete system prompt string
        """
        criteria_text = self._format_criteria(criteria, bands)
        extraction_text = self._format_extraction_fields(extraction_fields)
        
        format_kwargs = {
            "vertical_name": vertical_name,
            "criteria_text": criteria_text,
            "extraction_text": extraction_text,
        }
        
        if business_domain is not None:
            format_kwargs["business_domain"] = business_domain
        else:
            format_kwargs["business_domain"] = "null"
            
        if lead_type is not None:
            format_kwargs["lead_type"] = lead_type
        else:
            format_kwargs["lead_type"] = "null"
            
        if locale is not None:
            format_kwargs["locale"] = locale
        else:
            format_kwargs["locale"] = "null"
            
        if timestamp_utc is not None:
            format_kwargs["timestamp_utc"] = timestamp_utc
        else:
            format_kwargs["timestamp_utc"] = "null"
        
        try:
            prompt = self.system_template.format(**format_kwargs)
        except KeyError as e:
            missing_key = str(e).strip("'")
            # The template has literal { and } that are not placeholders
            # Escape them by doubling: { -> {{, } -> }}
            escaped_template = self.system_template.replace("{", "{{").replace("}", "}}")
            # Now unescape the placeholders we want to keep
            for key in format_kwargs:
                escaped_template = escaped_template.replace("{{" + key + "}}", "{" + key + "}")
            prompt = escaped_template.format(**format_kwargs)
        
        return prompt
    
    def _format_criteria(
        self,
        criteria: List[Dict[str, Any]],
        bands: List[Dict[str, Any]]
    ) -> str:
        """Format criteria with their bands for the prompt"""
        lines = []
        
        for i, criterion in enumerate(criteria, 1):
            criterion_key = criterion.get("criterion_key", "unknown")
            label = criterion.get("label", criterion_key)
            min_score = float(criterion.get("min_score", 0))
            max_score = float(criterion.get("max_score", 10))
            weight = float(criterion.get("weight", 1.0))
            
            lines.append(f"\n{i}. {criterion_key} ({min_score:.0f}-{max_score:.0f}): {label}")
            lines.append(f"   Peso: {weight:.1f}")
            
            criterion_bands = [
                b for b in bands 
                if b.get("criterion_id") == criterion.get("id") or b.get("criterion_id") == str(criterion.get("id"))
            ]
            
            if criterion_bands:
                lines.append("   Bandas:")
                for band in sorted(criterion_bands, key=lambda x: float(x.get("min_score", 0))):
                    band_key = band.get("band_key", "unknown")
                    band_label = band.get("label", band_key)
                    band_min = float(band.get("min_score", 0))
                    band_max = float(band.get("max_score", 10))
                    lines.append(f"   - {band_key} ({band_min:.0f}-{band_max:.0f}): {band_label}")
        
        return "\n".join(lines)
    
    def get_extraction_fields_from_prompt(self) -> List[Dict[str, Any]]:
        """Extract field names from JSON schema in prompt template"""
        import re
        
        fields = []
        
        extracted_data_match = re.search(
            r'"extracted_data"\s*:\s*\{(.+?)\n\s*\}',
            self.system_template,
            re.DOTALL
        )
        
        if extracted_data_match:
            extracted_data_block = extracted_data_match.group(1)
            field_matches = re.findall(r'"(\w+)"\s*:', extracted_data_block)
            
            for field_name in field_matches:
                fields.append({"key": field_name, "type": "string"})
        
        logger.info(f"Extracted fields from prompt: {fields}")
        return fields
    
    def _format_extraction_fields(
        self,
        extraction_fields: Optional[List[Dict[str, Any]]]
    ) -> str:
        """Format extraction fields for the prompt - now empty since they are in the DB prompt"""
        return ""
    
    def build_response_schema(
        self,
        criteria: List[Dict[str, Any]],
        extraction_fields: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Build JSON schema for structured LLM response.
        
        This schema is used to validate the LLM response and ensure
        it contains all expected fields.
        
        Args:
            criteria: List of criteria from lead_scoring_criteria
            extraction_fields: Optional list of fields to extract
        
        Returns:
            JSON schema dict for the response
        """
        score_properties = {}
        for criterion in criteria:
            criterion_key = criterion.get("criterion_key")
            if criterion_key:
                min_score = float(criterion.get("min_score", 0))
                max_score = float(criterion.get("max_score", 10))
                label = criterion.get("label", criterion_key)
                
                score_properties[criterion_key] = {
                    "type": "number",
                    "minimum": min_score,
                    "maximum": max_score,
                    "description": f"Score for {label} criterion"
                }
        
        extraction_properties = {}
        if extraction_fields:
            for field in extraction_fields:
                key = field.get("key")
                field_type = field.get("type", "string")
                description = field.get("description", "")
                
                if key:
                    extraction_properties[key] = {
                        "type": field_type if field_type in ["string", "number", "boolean"] else "string",
                        "description": description,
                        "nullable": True
                    }
        
        properties = {
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of the scoring decision"
            },
            "scores": {
                "type": "object",
                "properties": score_properties,
                "description": "Scores for each criterion"
            },
            "extracted_data": {
                "type": "object",
                "properties": extraction_properties,
                "description": "Extracted data from conversation"
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence score for the evaluation"
            }
        }
        
        required = ["reasoning", "scores", "extracted_data"]
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
