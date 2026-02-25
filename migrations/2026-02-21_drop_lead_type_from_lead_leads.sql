-- Remove legacy lead_type from lead_leads.
-- v2 routing now depends on tenant vertical_id/scoring_model_id.

BEGIN;

DROP INDEX IF EXISTS idx_lead_leads_lead_type;

ALTER TABLE IF EXISTS lead_leads
    DROP COLUMN IF EXISTS lead_type;

COMMIT;
