-- Migration 004: Refactor lead_scoring_models scope to vertical_id
-- Replaces client_id + lead_type with vertical_id (FK -> lead_client_verticals.id)

BEGIN;

-- 1) Add target column first (nullable during backfill)
ALTER TABLE lead_scoring_models
ADD COLUMN IF NOT EXISTS vertical_id INTEGER;

-- 2) Backfill from tenant association where available
UPDATE lead_scoring_models m
SET vertical_id = c.vertical_id
FROM lead_clients c
WHERE m.vertical_id IS NULL
  AND m.client_id IS NOT NULL
  AND c.id = m.client_id
  AND c.vertical_id IS NOT NULL;

-- 3) Backfill legacy lead_type-only rows using canonical vertical slugs
UPDATE lead_scoring_models m
SET vertical_id = v.id
FROM lead_client_verticals v
WHERE m.vertical_id IS NULL
  AND (
    (m.lead_type = 'realtor' AND v.slug = 'real-estate') OR
    (m.lead_type = 'automotriz' AND v.slug = 'automotive') OR
    (m.lead_type = 'medico' AND v.slug = 'healthcare') OR
    (m.lead_type = 'dental' AND v.slug = 'healthcare')
  );

-- 4) Enforce complete backfill before dropping old scope
DO $$
DECLARE
  missing_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO missing_count
  FROM lead_scoring_models
  WHERE vertical_id IS NULL;

  IF missing_count > 0 THEN
    RAISE EXCEPTION 'Migration blocked: % rows in lead_scoring_models still have NULL vertical_id', missing_count;
  END IF;
END $$;

-- 5) Drop old scope indexes first
DROP INDEX IF EXISTS idx_lead_scoring_models_client_lead_type_domain;
DROP INDEX IF EXISTS uq_lead_scoring_models_active_scope;
DROP INDEX IF EXISTS uq_lead_scoring_models_scope_name_version;

-- 6) Add FK and NOT NULL for vertical scope
ALTER TABLE lead_scoring_models
  ADD CONSTRAINT fk_lead_scoring_models_vertical
  FOREIGN KEY (vertical_id)
  REFERENCES lead_client_verticals(id);

ALTER TABLE lead_scoring_models
ALTER COLUMN vertical_id SET NOT NULL;

-- 7) Remove legacy scope columns
ALTER TABLE lead_scoring_models
DROP COLUMN IF EXISTS client_id,
DROP COLUMN IF EXISTS lead_type;

-- 8) Recreate scope indexes for vertical model
CREATE UNIQUE INDEX uq_lead_scoring_models_scope_name_version
  ON lead_scoring_models (vertical_id, COALESCE(business_domain, ''), name, version);

-- Keep one active model per (vertical_id, business_domain) before partial unique index.
WITH ranked_active AS (
  SELECT
    id,
    ROW_NUMBER() OVER (
      PARTITION BY vertical_id, COALESCE(business_domain, '')
      ORDER BY version DESC, updated_at DESC, created_at DESC
    ) AS rn
  FROM lead_scoring_models
  WHERE is_active = true
)
UPDATE lead_scoring_models m
SET is_active = false
FROM ranked_active r
WHERE m.id = r.id
  AND r.rn > 1;

CREATE UNIQUE INDEX uq_lead_scoring_models_active_scope
  ON lead_scoring_models (vertical_id, COALESCE(business_domain, ''))
  WHERE is_active = true;

CREATE INDEX idx_lead_scoring_models_vertical_domain
  ON lead_scoring_models (vertical_id, business_domain, is_active);

CREATE INDEX IF NOT EXISTS idx_lead_scoring_models_active
  ON lead_scoring_models (is_active)
  WHERE is_active = true;

COMMIT;
