-- Voice layer schema: call_queue + calls
-- Extends the base SDR schema (prospects, signals, messages tables assumed to exist)

CREATE TABLE IF NOT EXISTS call_queue (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_id        UUID NOT NULL,
    message_id         UUID,                          -- optional: the email that triggered this call
    priority           INT  NOT NULL DEFAULT 50,       -- higher = dispatched first
    status             TEXT NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending','dialing','completed','failed','cancelled','suppressed')),
    scheduled_for      TIMESTAMPTZ NOT NULL,
    earliest_at        TIMESTAMPTZ NOT NULL,           -- enforce call window lower bound
    latest_at          TIMESTAMPTZ NOT NULL,           -- abandon after this time
    attempt_count      INT  NOT NULL DEFAULT 0,
    vapi_call_id       TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_call_queue_status_sched
    ON call_queue (status, scheduled_for)
    WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS calls (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vapi_call_id     TEXT UNIQUE NOT NULL,
    call_queue_id    UUID REFERENCES call_queue(id),
    prospect_id      UUID NOT NULL,
    signal_type      TEXT,

    -- outcome
    outcome          TEXT CHECK (outcome IN (
                         'booked','not_interested','voicemail','no_answer',
                         'callback_requested','suppressed','transferred','error'
                     )),
    booked_meeting   BOOLEAN NOT NULL DEFAULT false,
    suppressed       BOOLEAN NOT NULL DEFAULT false,

    -- call details
    duration_seconds NUMERIC(8,1),
    model_used       TEXT,
    transcript_text  TEXT,
    messages         JSONB,
    recording_url    TEXT,
    cost_usd         NUMERIC(8,4),

    -- portal
    reviewed         BOOLEAN NOT NULL DEFAULT false,
    notes            TEXT,

    started_at       TIMESTAMPTZ,
    ended_at         TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_calls_prospect ON calls (prospect_id);
CREATE INDEX IF NOT EXISTS idx_calls_outcome  ON calls (outcome);
CREATE INDEX IF NOT EXISTS idx_calls_reviewed ON calls (reviewed) WHERE reviewed = false;

-- Auto-update updated_at on call_queue
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS call_queue_updated_at ON call_queue;
CREATE TRIGGER call_queue_updated_at
    BEFORE UPDATE ON call_queue
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
