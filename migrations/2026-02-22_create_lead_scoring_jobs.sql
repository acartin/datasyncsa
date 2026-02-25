-- Persistent async scoring jobs for inference-stack v2.

CREATE TABLE IF NOT EXISTS lead_scoring_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES lead_leads(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL,
    client_id UUID NOT NULL,
    model_id UUID NULL,
    prompt_id UUID NULL,
    expected_lead_messages INTEGER NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    scheduled_for TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    last_error_code VARCHAR(64) NULL,
    last_error_message TEXT NULL,
    fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
    json_valid BOOLEAN NULL,
    latency_ms INTEGER NULL,
    response_chars INTEGER NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_lead_scoring_jobs_status
        CHECK (status IN ('queued', 'running', 'rescheduled', 'completed', 'degraded', 'failed', 'cancelled'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_lead_scoring_jobs_conversation
    ON lead_scoring_jobs(conversation_id);

CREATE INDEX IF NOT EXISTS idx_lead_scoring_jobs_status_scheduled
    ON lead_scoring_jobs(status, scheduled_for);

CREATE INDEX IF NOT EXISTS idx_lead_scoring_jobs_lead_created
    ON lead_scoring_jobs(lead_id, created_at DESC);

CREATE OR REPLACE FUNCTION lead_scoring_jobs_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'trg_lead_scoring_jobs_updated_at'
    ) THEN
        CREATE TRIGGER trg_lead_scoring_jobs_updated_at
        BEFORE UPDATE ON lead_scoring_jobs
        FOR EACH ROW
        EXECUTE FUNCTION lead_scoring_jobs_set_updated_at();
    END IF;
END $$;
