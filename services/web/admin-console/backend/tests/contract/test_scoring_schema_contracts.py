"""
Contract tests for scoring schema SDUI contracts.
Validates shape and compatibility of scoring v2 contracts.
"""
import pytest
from uuid import UUID, uuid4
from app.contracts.scoring_schema import (
    ScoringSchemaV2,
    ScoringValuesV2,
    ScoringCriterionV2,
    ScoringBandV2,
    ScoreItemValueV2,
    DynamicLeadGridColumn,
    DynamicGridConfig
)


class TestScoringSchemaContracts:
    """Tests for ScoringSchemaV2 and related contracts."""
    
    def test_scoring_schema_v2_basic_shape(self):
        """Test basic shape of ScoringSchemaV2."""
        schema = ScoringSchemaV2(
            lead_type="realtor",
            model_id=uuid4(),
            model_version=1,
            prompt_version=1,
            criteria=[],
            normalization_strategy="weighted_sum"
        )
        
        assert schema.lead_type == "realtor"
        assert isinstance(schema.model_id, UUID)
        assert schema.model_version == 1
        assert schema.prompt_version == 1
        assert schema.criteria == []
        assert schema.normalization_strategy == "weighted_sum"
    
    def test_scoring_criterion_with_bands(self):
        """Test ScoringCriterionV2 with bands."""
        criterion = ScoringCriterionV2(
            criterion_key="intent",
            label="Intención de Compra",
            weight=0.3,
            min_score=0.0,
            max_score=100.0,
            display_order=1,
            bands=[
                ScoringBandV2(
                    band_key="low",
                    label="Baja",
                    min_score=0.0,
                    max_score=33.0,
                    icon="ri-arrow-down-line",
                    color="danger"
                ),
                ScoringBandV2(
                    band_key="medium",
                    label="Media",
                    min_score=33.0,
                    max_score=66.0,
                    icon="ri-arrow-right-line",
                    color="warning"
                ),
                ScoringBandV2(
                    band_key="high",
                    label="Alta",
                    min_score=66.0,
                    max_score=100.0,
                    icon="ri-arrow-up-line",
                    color="success"
                )
            ]
        )
        
        assert criterion.criterion_key == "intent"
        assert criterion.weight == 0.3
        assert len(criterion.bands) == 3
        assert criterion.bands[0].band_key == "low"
        assert criterion.bands[2].band_key == "high"
    
    def test_scoring_values_v2_complete(self):
        """Test complete ScoringValuesV2."""
        values = ScoringValuesV2(
            score_total=85.5,
            priority_label="Alta Prioridad",
            reasoning="Lead muestra alto interés en propiedades premium",
            score_items=[
                ScoreItemValueV2(
                    criterion_key="intent",
                    score=90.0,
                    band_key="high",
                    band_label="Alta",
                    band_color="success",
                    band_icon="ri-arrow-up-line",
                    explanation="Múltiples preguntas sobre financiamiento",
                    normalized_score=90.0
                ),
                ScoreItemValueV2(
                    criterion_key="urgency",
                    score=75.0,
                    band_key="medium",
                    band_label="Media",
                    band_color="warning",
                    band_icon="ri-arrow-right-line",
                    explanation="Planeando compra en 3-6 meses",
                    normalized_score=75.0
                )
            ],
            scorecard_id=uuid4(),
            created_at="2024-01-15T10:30:00Z"
        )
        
        assert values.score_total == 85.5
        assert values.priority_label == "Alta Prioridad"
        assert len(values.score_items) == 2
        assert values.score_items[0].criterion_key == "intent"
        assert values.score_items[1].criterion_key == "urgency"
        assert values.score_items[0].normalized_score == 90.0
    
    def test_dynamic_grid_column(self):
        """Test DynamicLeadGridColumn."""
        column = DynamicLeadGridColumn(
            id="scoring_intent",
            label="Intención",
            type="scoring-pillar",
            sortable=True,
            width="150px",
            icon="ri-target-line",
            criterion_key="intent"
        )
        
        assert column.id == "scoring_intent"
        assert column.label == "Intención"
        assert column.type == "scoring-pillar"
        assert column.sortable is True
        assert column.criterion_key == "intent"
    
    def test_dynamic_grid_config(self):
        """Test DynamicGridConfig."""
        columns = [
            DynamicLeadGridColumn(
                id="identity",
                label="Lead",
                type="gauge-identity",
                sortable=True,
                width="250px"
            ),
            DynamicLeadGridColumn(
                id="scoring_intent",
                label="Intención",
                type="scoring-pillar",
                sortable=True,
                criterion_key="intent"
            )
        ]
        
        config = DynamicGridConfig(
            grid_id="leads-v2-realtor",
            data_url="/leads_v2/data?lead_type=realtor",
            enable_filters=True,
            columns=columns,
            filter_config={
                "searchFields": ["full_name", "email"],
                "filterableColumns": [
                    {"id": "identity", "label": "Lead", "icon": "ri-shield-user-line"},
                    {"id": "scoring_intent", "label": "Intención", "icon": "ri-target-line"}
                ]
            },
            actions=[
                {"label": "Ver Detalle", "icon": "ri-eye-line", "action": "navigate", "action_url": "/dashboard/leads_v2/{id}"}
            ]
        )
        
        assert config.grid_id == "leads-v2-realtor"
        assert config.data_url == "/leads_v2/data?lead_type=realtor"
        assert config.enable_filters is True
        assert len(config.columns) == 2
        assert config.columns[0].id == "identity"
        assert config.columns[1].id == "scoring_intent"
        assert "searchFields" in config.filter_config
        assert len(config.actions) == 1
    
    def test_scoring_schema_validation(self):
        """Test validation rules in scoring schema."""
        # Weight must be between 0 and 1
        with pytest.raises(ValueError):
            ScoringCriterionV2(
                criterion_key="test",
                label="Test",
                weight=1.5,  # Invalid: > 1
                min_score=0.0,
                max_score=100.0,
                display_order=1,
                bands=[]
            )
        
        # Score must be >= 0
        with pytest.raises(ValueError):
            ScoreItemValueV2(
                criterion_key="test",
                score=-10.0,  # Invalid: < 0
                band_key="low"
            )
        
        # Model version must be > 0
        with pytest.raises(ValueError):
            ScoringSchemaV2(
                lead_type="test",
                model_id=uuid4(),
                model_version=0,  # Invalid: <= 0
                prompt_version=1,
                criteria=[]
            )
    
    def test_compatibility_with_legacy_fallback(self):
        """Test that contracts support legacy fallback scenarios."""
        # Empty scoring values (no scorecard)
        empty_values = ScoringValuesV2(
            score_total=0.0,
            score_items=[]
        )
        
        assert empty_values.score_total == 0.0
        assert empty_values.score_items == []
        assert empty_values.priority_label is None
        assert empty_values.reasoning is None
        assert empty_values.scorecard_id is None
        
        # Partial scoring values (some fields missing)
        partial_values = ScoringValuesV2(
            score_total=65.0,
            score_items=[
                ScoreItemValueV2(
                    criterion_key="urgency",
                    score=65.0,
                    band_key="medium"
                )
            ]
        )
        
        assert partial_values.score_total == 65.0
        assert len(partial_values.score_items) == 1
        assert partial_values.score_items[0].band_label is None
        assert partial_values.score_items[0].explanation is None


class TestContractCompatibility:
    """Tests for forward/backward compatibility."""
    
    def test_scoring_schema_serialization(self):
        """Test that scoring schema can be serialized/deserialized."""
        schema = ScoringSchemaV2(
            lead_type="medical",
            model_id=uuid4(),
            model_version=2,
            prompt_version=1,
            criteria=[
                ScoringCriterionV2(
                    criterion_key="symptom_severity",
                    label="Severidad de Síntomas",
                    weight=0.4,
                    min_score=0.0,
                    max_score=10.0,
                    display_order=1,
                    bands=[
                        ScoringBandV2(
                            band_key="mild",
                            label="Leve",
                            min_score=0.0,
                            max_score=3.0,
                            icon="ri-heart-line",
                            color="success"
                        )
                    ]
                )
            ]
        )
        
        # Serialize to dict
        schema_dict = schema.model_dump()
        
        # Deserialize back
        schema_restored = ScoringSchemaV2(**schema_dict)
        
        assert schema_restored.lead_type == schema.lead_type
        assert schema_restored.model_version == schema.model_version
        assert len(schema_restored.criteria) == len(schema.criteria)
        assert schema_restored.criteria[0].criterion_key == schema.criteria[0].criterion_key
    
    def test_metadata_fields_preserved(self):
        """Test that extra metadata fields are preserved in serialization."""
        values = ScoringValuesV2(
            score_total=75.0,
            score_items=[],
            metadata={"custom_field": "custom_value"}  # Extra field
        )
        
        values_dict = values.model_dump()
        
        # Pydantic should preserve extra fields with extra="allow"
        assert "metadata" in values_dict
        assert values_dict["metadata"]["custom_field"] == "custom_value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])