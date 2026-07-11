-- Sentinel — Migration 003: persist amount_at_risk for expected-loss triage (#24)
--
-- The queue (Home tab + console) should rank by EXPECTED LOSS = risk × amount,
-- not by risk % alone. That requires the dollar amount at risk to be stored on
-- the case. Nullable / defaulted so existing rows and the Slack path (which may
-- not know the amount) stay valid.

ALTER TABLE cases ADD COLUMN IF NOT EXISTS amount_at_risk NUMERIC(14,2) DEFAULT 0;
