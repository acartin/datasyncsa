-- Migration 001: Initial scoring v2 schema
-- Implements the decoupled scoring system from RFC Section 5

-- Required extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================
-- 1. lead_scoring_models
-- ============================================
CREATE TABLE lead_scoring_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NULL, -- nullable for global models
    lead_type VARCHAR(32) NOT NULL,
    business_domain VARCHAR(64) NULL,
    name VARCHAR(128) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    prompt_version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT true,
    normalization_strategy VARCHAR(64) NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Comments
    CONSTRAINT valid_version CHECK (version > 0),
    CONSTRAINT valid_prompt_version CHECK (prompt_version > 0)
);

COMMENT ON TABLE lead_scoring_models IS 'Define el modelo activo por tipo/tenant';
COMMENT ON COLUMN lead_scoring_models.id IS 'Primary key UUID';
COMMENT ON COLUMN lead_scoring_models.client_id IS 'Tenant/client ID (nullable para modelos globales)';
COMMENT ON COLUMN lead_scoring_models.lead_type IS 'Tipo de lead (ej: realtor, medico, dental, automotriz)';
COMMENT ON COLUMN lead_scoring_models.business_domain IS 'Dominio de negocio opcional para granularidad adicional';
COMMENT ON COLUMN lead_scoring_models.name IS 'Nombre descriptivo del modelo';
COMMENT ON COLUMN lead_scoring_models.version IS 'Versión del modelo (incremental)';
COMMENT ON COLUMN lead_scoring_models.prompt_version IS 'Versión de prompt acoplada al modelo activo';
COMMENT ON COLUMN lead_scoring_models.is_active IS 'Indica si el modelo está activo para uso';
COMMENT ON COLUMN lead_scoring_models.normalization_strategy IS 'Estrategia de normalización de scores (ej: weighted_sum, min_max)';
COMMENT ON COLUMN lead_scoring_models.created_at IS 'Fecha de creación del registro';
COMMENT ON COLUMN lead_scoring_models.updated_at IS 'Fecha de última actualización';

-- ============================================
-- 2. lead_scoring_criteria
-- ============================================
CREATE TABLE lead_scoring_criteria (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID NOT NULL,
    criterion_key VARCHAR(64) NOT NULL,
    label VARCHAR(128) NOT NULL,
    weight DECIMAL(5,2) NOT NULL DEFAULT 1.0,
    min_score DECIMAL(5,2) NOT NULL DEFAULT 0.0,
    max_score DECIMAL(5,2) NOT NULL DEFAULT 10.0,
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key to models
    CONSTRAINT fk_lead_scoring_criteria_model
        FOREIGN KEY (model_id)
        REFERENCES lead_scoring_models(id)
        ON DELETE CASCADE,
    
    -- Constraints
    UNIQUE(model_id, criterion_key),
    CONSTRAINT valid_weight CHECK (weight >= 0.0),
    CONSTRAINT valid_score_range CHECK (min_score <= max_score),
    CONSTRAINT positive_display_order CHECK (display_order >= 0)
);

COMMENT ON TABLE lead_scoring_criteria IS 'Define pilares dinámicos de scoring';
COMMENT ON COLUMN lead_scoring_criteria.id IS 'Primary key UUID';
COMMENT ON COLUMN lead_scoring_criteria.model_id IS 'Referencia al modelo de scoring';
COMMENT ON COLUMN lead_scoring_criteria.criterion_key IS 'Clave única del criterio (ej: intent, urgency, data_quality)';
COMMENT ON COLUMN lead_scoring_criteria.label IS 'Etiqueta descriptiva para UI';
COMMENT ON COLUMN lead_scoring_criteria.weight IS 'Peso del criterio en cálculo total';
COMMENT ON COLUMN lead_scoring_criteria.min_score IS 'Valor mínimo posible para este criterio';
COMMENT ON COLUMN lead_scoring_criteria.max_score IS 'Valor máximo posible para este criterio';
COMMENT ON COLUMN lead_scoring_criteria.display_order IS 'Orden de visualización en UI';
COMMENT ON COLUMN lead_scoring_criteria.is_active IS 'Indica si el criterio está activo';
COMMENT ON COLUMN lead_scoring_criteria.created_at IS 'Fecha de creación del registro';
COMMENT ON COLUMN lead_scoring_criteria.updated_at IS 'Fecha de última actualización';

-- ============================================
-- 3. lead_scoring_bands
-- ============================================
CREATE TABLE lead_scoring_bands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    criterion_id UUID NOT NULL,
    band_key VARCHAR(32) NOT NULL,
    label VARCHAR(64) NOT NULL,
    min_score DECIMAL(5,2) NOT NULL,
    max_score DECIMAL(5,2) NOT NULL,
    icon VARCHAR(128) NULL,
    color VARCHAR(32) NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key to criteria
    CONSTRAINT fk_lead_scoring_bands_criterion
        FOREIGN KEY (criterion_id)
        REFERENCES lead_scoring_criteria(id)
        ON DELETE CASCADE,
    
    -- Constraints
    UNIQUE(criterion_id, band_key),
    CONSTRAINT valid_band_score_range CHECK (min_score < max_score)
);

COMMENT ON TABLE lead_scoring_bands IS 'Bandas visuales por criterio para categorización de scores';
COMMENT ON COLUMN lead_scoring_bands.id IS 'Primary key UUID';
COMMENT ON COLUMN lead_scoring_bands.criterion_id IS 'Referencia al criterio padre';
COMMENT ON COLUMN lead_scoring_bands.band_key IS 'Clave única de banda (ej: low, medium, high, critical)';
COMMENT ON COLUMN lead_scoring_bands.label IS 'Etiqueta descriptiva para UI';
COMMENT ON COLUMN lead_scoring_bands.min_score IS 'Límite inferior de la banda (inclusive)';
COMMENT ON COLUMN lead_scoring_bands.max_score IS 'Límite superior de la banda (exclusive)';
COMMENT ON COLUMN lead_scoring_bands.icon IS 'Ícono para representación visual';
COMMENT ON COLUMN lead_scoring_bands.color IS 'Color CSS para representación visual';
COMMENT ON COLUMN lead_scoring_bands.created_at IS 'Fecha de creación del registro';
COMMENT ON COLUMN lead_scoring_bands.updated_at IS 'Fecha de última actualización';

-- ============================================
-- 4. lead_scorecards
-- ============================================
CREATE TABLE lead_scorecards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL,
    conversation_id UUID NULL,
    model_id UUID NOT NULL,
    model_version INTEGER NOT NULL,
    prompt_version INTEGER NOT NULL,
    score_total DECIMAL(5,2) NOT NULL,
    priority_label VARCHAR(32) NULL,
    reasoning TEXT NULL,
    raw_payload JSONB NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys
    CONSTRAINT fk_lead_scorecards_lead
        FOREIGN KEY (lead_id)
        REFERENCES lead_leads(id)
        ON DELETE CASCADE,

    -- Note: conversation_id references conversation_chats.id (if applicable)
    
    CONSTRAINT fk_lead_scorecards_model
        FOREIGN KEY (model_id)
        REFERENCES lead_scoring_models(id),
    
    -- Constraints
    CONSTRAINT valid_total_score CHECK (score_total >= 0.0),
    CONSTRAINT valid_scorecard_model_version CHECK (model_version > 0),
    CONSTRAINT valid_scorecard_prompt_version CHECK (prompt_version > 0)
);

COMMENT ON TABLE lead_scorecards IS 'Evaluación completa de un lead en un instante';
COMMENT ON COLUMN lead_scorecards.id IS 'Primary key UUID';
COMMENT ON COLUMN lead_scorecards.lead_id IS 'Referencia al lead evaluado';
COMMENT ON COLUMN lead_scorecards.conversation_id IS 'Referencia a la conversación que generó el score (opcional)';
COMMENT ON COLUMN lead_scorecards.model_id IS 'Referencia al modelo de scoring usado';
COMMENT ON COLUMN lead_scorecards.model_version IS 'Versión inmutable del modelo al momento de evaluar';
COMMENT ON COLUMN lead_scorecards.prompt_version IS 'Versión inmutable del prompt al momento de evaluar';
COMMENT ON COLUMN lead_scorecards.score_total IS 'Score total normalizado del lead';
COMMENT ON COLUMN lead_scorecards.priority_label IS 'Etiqueta de prioridad derivada del score';
COMMENT ON COLUMN lead_scorecards.reasoning IS 'Razonamiento textual del scoring';
COMMENT ON COLUMN lead_scorecards.raw_payload IS 'Payload raw del proceso de scoring (JSONB)';
COMMENT ON COLUMN lead_scorecards.created_at IS 'Fecha de creación de la evaluación';

-- ============================================
-- 5. lead_score_items
-- ============================================
CREATE TABLE lead_score_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scorecard_id UUID NOT NULL,
    criterion_key VARCHAR(64) NOT NULL,
    score DECIMAL(5,2) NOT NULL,
    band_id UUID NULL,
    explanation TEXT NULL,
    extracted_data JSONB NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys
    CONSTRAINT fk_lead_score_items_scorecard
        FOREIGN KEY (scorecard_id)
        REFERENCES lead_scorecards(id)
        ON DELETE CASCADE,
    
    CONSTRAINT fk_lead_score_items_band
        FOREIGN KEY (band_id)
        REFERENCES lead_scoring_bands(id),
    
    -- Constraints
    CONSTRAINT valid_item_score CHECK (score >= 0.0),
    CONSTRAINT uq_lead_score_items_scorecard_criterion UNIQUE (scorecard_id, criterion_key)
);

COMMENT ON TABLE lead_score_items IS 'Detalle por pilar de una scorecard';
COMMENT ON COLUMN lead_score_items.id IS 'Primary key UUID';
COMMENT ON COLUMN lead_score_items.scorecard_id IS 'Referencia a la scorecard padre';
COMMENT ON COLUMN lead_score_items.criterion_key IS 'Clave del criterio evaluado';
COMMENT ON COLUMN lead_score_items.score IS 'Score específico para este criterio';
COMMENT ON COLUMN lead_score_items.band_id IS 'Referencia a la banda visual aplicada (opcional)';
COMMENT ON COLUMN lead_score_items.explanation IS 'Explicación textual del score para este criterio';
COMMENT ON COLUMN lead_score_items.extracted_data IS 'Datos extraídos del análisis (JSONB)';
COMMENT ON COLUMN lead_score_items.created_at IS 'Fecha de creación del ítem';

-- ============================================
-- 6. Alter table lead_leads
-- ============================================
ALTER TABLE lead_leads
ADD COLUMN lead_type VARCHAR(32) NOT NULL DEFAULT 'realtor',
ADD COLUMN business_domain VARCHAR(64) NULL,
ADD COLUMN current_scorecard_id UUID NULL;

ALTER TABLE lead_leads
ADD CONSTRAINT fk_lead_leads_current_scorecard
    FOREIGN KEY (current_scorecard_id)
    REFERENCES lead_scorecards(id)
    ON DELETE SET NULL;

COMMENT ON COLUMN lead_leads.lead_type IS 'Tipo de lead para routing de scoring (realtor, medico, dental, etc.)';
COMMENT ON COLUMN lead_leads.business_domain IS 'Dominio de negocio opcional para granularidad adicional';
COMMENT ON COLUMN lead_leads.current_scorecard_id IS 'Referencia a la scorecard vigente para acceso rápido';

-- ============================================
-- 7. Indexes for performance
-- ============================================

-- Indexes for lead_scoring_models
CREATE UNIQUE INDEX uq_lead_scoring_models_scope_name_version
    ON lead_scoring_models(
        COALESCE(client_id, '00000000-0000-0000-0000-000000000000'::UUID),
        lead_type,
        COALESCE(business_domain, ''),
        name,
        version
    );

CREATE INDEX idx_lead_scoring_models_client_lead_type_domain
    ON lead_scoring_models(client_id, lead_type, business_domain, is_active);

CREATE UNIQUE INDEX uq_lead_scoring_models_active_scope
    ON lead_scoring_models(
        COALESCE(client_id, '00000000-0000-0000-0000-000000000000'::UUID),
        lead_type,
        COALESCE(business_domain, '')
    )
    WHERE is_active = true;

CREATE INDEX idx_lead_scoring_models_active 
    ON lead_scoring_models(is_active) WHERE is_active = true;

-- Indexes for lead_scoring_criteria
CREATE INDEX idx_lead_scoring_criteria_model 
    ON lead_scoring_criteria(model_id);

CREATE INDEX idx_lead_scoring_criteria_active 
    ON lead_scoring_criteria(is_active) WHERE is_active = true;

-- Indexes for lead_scoring_bands
CREATE INDEX idx_lead_scoring_bands_criterion 
    ON lead_scoring_bands(criterion_id);

-- Indexes for lead_scorecards
CREATE INDEX idx_lead_scorecards_lead 
    ON lead_scorecards(lead_id);

CREATE INDEX idx_lead_scorecards_lead_created 
    ON lead_scorecards(lead_id, created_at DESC);

CREATE INDEX idx_lead_scorecards_conversation 
    ON lead_scorecards(conversation_id) WHERE conversation_id IS NOT NULL;

CREATE INDEX idx_lead_scorecards_model 
    ON lead_scorecards(model_id);

CREATE INDEX idx_lead_scorecards_model_version
    ON lead_scorecards(model_id, model_version, prompt_version);

-- Indexes for lead_score_items
CREATE INDEX idx_lead_score_items_scorecard 
    ON lead_score_items(scorecard_id);

CREATE INDEX idx_lead_score_items_criterion_key 
    ON lead_score_items(criterion_key);

-- Indexes for lead_leads (new columns)
CREATE INDEX idx_lead_leads_lead_type 
    ON lead_leads(lead_type);

CREATE INDEX idx_lead_leads_business_domain 
    ON lead_leads(business_domain) WHERE business_domain IS NOT NULL;

CREATE INDEX idx_lead_leads_current_scorecard 
    ON lead_leads(current_scorecard_id) WHERE current_scorecard_id IS NOT NULL;

-- ============================================
-- 8. Validation trigger for non-overlapping bands
-- ============================================
CREATE OR REPLACE FUNCTION validate_scoring_band_overlap()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM lead_scoring_bands b
        WHERE b.criterion_id = NEW.criterion_id
          AND b.id <> COALESCE(NEW.id, '00000000-0000-0000-0000-000000000000'::UUID)
          AND NEW.min_score < b.max_score
          AND NEW.max_score > b.min_score
    ) THEN
        RAISE EXCEPTION 'Overlapping scoring bands for criterion_id=%', NEW.criterion_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_scoring_band_overlap
    BEFORE INSERT OR UPDATE ON lead_scoring_bands
    FOR EACH ROW
    EXECUTE FUNCTION validate_scoring_band_overlap();

-- ============================================
-- 9. Triggers for updated_at
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for lead_scoring_models
CREATE TRIGGER update_lead_scoring_models_updated_at
    BEFORE UPDATE ON lead_scoring_models
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for lead_scoring_criteria
CREATE TRIGGER update_lead_scoring_criteria_updated_at
    BEFORE UPDATE ON lead_scoring_criteria
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for lead_scoring_bands
CREATE TRIGGER update_lead_scoring_bands_updated_at
    BEFORE UPDATE ON lead_scoring_bands
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 10. Migration complete
-- ============================================

-- Migration 001: Initial scoring v2 schema created successfully
-- This implements the decoupled scoring system as per RFC Section 5
