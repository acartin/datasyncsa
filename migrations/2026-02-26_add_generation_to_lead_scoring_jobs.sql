BEGIN;

ALTER TABLE lead_scoring_jobs
    ADD COLUMN IF NOT EXISTS generation BIGINT NOT NULL DEFAULT 1;

ALTER TABLE lead_scoring_jobs
    ADD COLUMN IF NOT EXISTS running_generation BIGINT NULL;

COMMIT;
