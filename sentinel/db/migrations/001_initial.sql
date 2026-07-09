-- Sentinel — Initial Schema Migration
-- Run once on a fresh database. Docker Compose auto-runs this via the
-- /docker-entrypoint-initdb.d/ mount on first container start.

-- ── Extension ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- for gen_random_uuid()

-- ── Users (Slack identity index) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slack_id        TEXT UNIQUE NOT NULL,        -- Slack user ID e.g. U0123456789
    display_name    TEXT,
    hmac_alias      TEXT,                        -- format-preserving pseudonym (ticket #4)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_slack_id ON users (slack_id);

-- ── Cases ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cases (
    case_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slack_channel    TEXT NOT NULL,              -- C0123456789
    slack_ts         TEXT NOT NULL,              -- originating message timestamp (thread root)
    reporter_slack_id TEXT NOT NULL,             -- U0123456789 (raw — gateway de-aliases)
    status           TEXT NOT NULL DEFAULT 'created'
                        CHECK (status IN ('created','analyzing','verdict','resolved')),
    risk_score       NUMERIC(5,4),               -- 0.0000 – 1.0000
    verdict          TEXT CHECK (verdict IN ('FRAUD_LIKELY','REVIEW','CLEAR')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases (status);
CREATE INDEX IF NOT EXISTS idx_cases_created ON cases (created_at DESC);

-- ── Evidence ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID NOT NULL REFERENCES cases (case_id) ON DELETE CASCADE,
    evidence_type   TEXT NOT NULL DEFAULT 'file'
                        CHECK (evidence_type IN ('file','message','voice','url')),
    file_url        TEXT,                        -- Slack CDN URL if a file
    raw_metrics     JSONB NOT NULL DEFAULT '{}', -- pre-extracted metrics blob
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence (case_id);

-- ── Agent Results ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_results (
    result_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID NOT NULL REFERENCES cases (case_id) ON DELETE CASCADE,
    agent_name      TEXT NOT NULL,               -- 'vision' | 'finance' | 'stylometric' | …
    claims          JSONB NOT NULL DEFAULT '[]', -- serialised Claim list
    contradictions  JSONB NOT NULL DEFAULT '[]', -- serialised Contradiction list
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_results_case ON agent_results (case_id);

-- ── Synthesized Rules (ticket #26) ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS synthesized_rules (
    rule_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_case_id  UUID REFERENCES cases (case_id),
    rule_json       JSONB NOT NULL DEFAULT '{}', -- structured JSON rule schema
    status          TEXT NOT NULL DEFAULT 'shadow'
                        CHECK (status IN ('shadow','enforced','retired')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rules_status ON synthesized_rules (status);

-- ── Hash-Chained Audit Log (ticket #27) ──────────────────────────────────────
-- append-only: no UPDATE or DELETE permissions should be granted on this table
CREATE TABLE IF NOT EXISTS audit_chain (
    entry_id        BIGSERIAL PRIMARY KEY,
    case_id         UUID REFERENCES cases (case_id),
    event_type      TEXT NOT NULL,               -- 'case_created' | 'verdict' | 'quarantine' | …
    payload         JSONB NOT NULL DEFAULT '{}',
    prev_hash       TEXT NOT NULL DEFAULT '',    -- SHA-256 hex of previous entry
    entry_hash      TEXT NOT NULL,               -- SHA-256 hex of this entry
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- No index on audit_chain intentionally — sequential scan keeps proof-of-order semantics.

-- ── Case Embeddings stub (for ticket #21 semantic recall) ────────────────────
CREATE TABLE IF NOT EXISTS case_embeddings (
    embedding_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID NOT NULL REFERENCES cases (case_id) ON DELETE CASCADE,
    model           TEXT NOT NULL DEFAULT 'text-embedding-3-small',
    embedding       TEXT,                        -- JSON array string until pgvector is added
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_embeddings_case ON case_embeddings (case_id, model);

-- ── Helper: auto-update updated_at on cases ──────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_cases_updated_at ON cases;
CREATE TRIGGER trg_cases_updated_at
    BEFORE UPDATE ON cases
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
