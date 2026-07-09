"""Test environment bootstrap — runs before every test module.

Sets the env vars that sentinel.slack_app, sentinel.db.pool, and
sentinel.gateway need at import time. These are placeholder values
that allow the modules to import cleanly; they do NOT point to a real
Slack workspace or live database unless you have Docker running.

Tests that actually hit the DB (marked `integration`) require:
    docker compose up -d
"""

import os

# Slack — any non-empty strings let Bolt import without error.
# Real investigations obviously need real tokens (see .env.example).
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-placeholder")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-signing-secret-placeholder-32c")
os.environ.setdefault("SLACK_APP_TOKEN", "xapp-test-placeholder")

# Database — matches docker-compose.yml defaults
os.environ.setdefault("DATABASE_URL", "postgresql://sentinel:sentinel@localhost:5432/sentinel")

# PII gateway pepper
os.environ.setdefault("PII_HMAC_PEPPER", "test-pepper-not-for-production")
