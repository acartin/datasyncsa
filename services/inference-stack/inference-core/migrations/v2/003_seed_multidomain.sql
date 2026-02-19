-- Migration 003: Seed additional lead_type templates (idempotent)
-- Seeds global default models for: medico, dental, automotriz.

BEGIN;

DO $$
DECLARE
    v_lead_type TEXT;
    v_model_name TEXT;
    v_model_id UUID;
    v_criterion RECORD;
BEGIN
    FOR v_lead_type IN
        SELECT unnest(ARRAY['medico', 'dental', 'automotriz'])
    LOOP
        v_model_name := initcap(v_lead_type) || ' Default v1';
        v_model_id := NULL;

        -- Resolve or create canonical global model (client_id NULL, domain NULL).
        SELECT id
        INTO v_model_id
        FROM lead_scoring_models
        WHERE client_id IS NULL
          AND lead_type = v_lead_type
          AND business_domain IS NULL
          AND name = v_model_name
          AND version = 1
        LIMIT 1;

        IF v_model_id IS NULL THEN
            -- Keep one active model per scope.
            UPDATE lead_scoring_models
            SET is_active = FALSE
            WHERE client_id IS NULL
              AND lead_type = v_lead_type
              AND business_domain IS NULL
              AND is_active = TRUE;

            INSERT INTO lead_scoring_models (
                client_id,
                lead_type,
                business_domain,
                name,
                version,
                prompt_version,
                is_active,
                normalization_strategy
            )
            VALUES (
                NULL,
                v_lead_type,
                NULL,
                v_model_name,
                1,
                1,
                TRUE,
                'weighted_sum'
            )
            RETURNING id INTO v_model_id;
        ELSE
            UPDATE lead_scoring_models
            SET prompt_version = 1,
                normalization_strategy = 'weighted_sum',
                is_active = TRUE
            WHERE id = v_model_id;

            UPDATE lead_scoring_models
            SET is_active = FALSE
            WHERE client_id IS NULL
              AND lead_type = v_lead_type
              AND business_domain IS NULL
              AND id <> v_model_id
              AND is_active = TRUE;
        END IF;

        INSERT INTO lead_scoring_criteria (
            model_id,
            criterion_key,
            label,
            weight,
            min_score,
            max_score,
            display_order,
            is_active
        )
        VALUES
            (v_model_id, 'intent',       'Intent',       1.00, 0.00, 10.00, 10, TRUE),
            (v_model_id, 'urgency',      'Urgency',      1.00, 0.00, 10.00, 20, TRUE),
            (v_model_id, 'data_quality', 'Data Quality', 1.00, 0.00, 10.00, 30, TRUE),
            (v_model_id, 'engagement',   'Engagement',   1.00, 0.00, 10.00, 40, TRUE)
        ON CONFLICT (model_id, criterion_key) DO UPDATE
        SET label = EXCLUDED.label,
            weight = EXCLUDED.weight,
            min_score = EXCLUDED.min_score,
            max_score = EXCLUDED.max_score,
            display_order = EXCLUDED.display_order,
            is_active = EXCLUDED.is_active;

        FOR v_criterion IN
            SELECT id
            FROM lead_scoring_criteria
            WHERE model_id = v_model_id
              AND criterion_key IN ('intent', 'urgency', 'data_quality', 'engagement')
        LOOP
            INSERT INTO lead_scoring_bands (
                criterion_id,
                band_key,
                label,
                min_score,
                max_score,
                icon,
                color
            )
            VALUES
                (v_criterion.id, 'low',    'Low',    0.00, 3.00, 'thermometer-low',  '#4A90E2'),
                (v_criterion.id, 'medium', 'Medium', 3.00, 7.00, 'thermometer-mid',  '#F5A623'),
                (v_criterion.id, 'high',   'High',   7.00, 10.00, 'thermometer-high', '#D0021B')
            ON CONFLICT (criterion_id, band_key) DO UPDATE
            SET label = EXCLUDED.label,
                min_score = EXCLUDED.min_score,
                max_score = EXCLUDED.max_score,
                icon = EXCLUDED.icon,
                color = EXCLUDED.color;
        END LOOP;
    END LOOP;
END $$;

COMMIT;

