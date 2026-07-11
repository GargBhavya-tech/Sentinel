-- Sentinel — Migration 002: allow the NEED_MORE_INFO verdict
--
-- The Confidence-Calibrated Silence path (sse_worker._check_silence) sets
-- verdict = 'NEED_MORE_INFO' when evidence is too thin to cross-examine, but
-- the original CHECK constraint only permitted FRAUD_LIKELY / REVIEW / CLEAR.
-- Writing the silence verdict therefore raised an IntegrityError and the case
-- never persisted. Widen the constraint to include it.

ALTER TABLE cases DROP CONSTRAINT IF EXISTS cases_verdict_check;
ALTER TABLE cases ADD CONSTRAINT cases_verdict_check
    CHECK (verdict IN ('FRAUD_LIKELY','REVIEW','CLEAR','NEED_MORE_INFO'));
