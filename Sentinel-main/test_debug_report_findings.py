"""
Regression tests for Sentinel_Debug_Report.md.

Drop this file into `tests/` and run:
    pytest tests/test_debug_report_findings.py -v

Status key (as of the report):
  [RED]   test currently FAILS — it reproduces a real bug. It should turn
          green once the corresponding fix lands, and MUST stay green after.
  [GREEN] test currently PASSES — it's a guard against a fix regressing,
          or confirms something that was already fine.

None of these require Slack or a live Postgres connection.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import psycopg  # type: ignore

from sentinel.db import repo


# ─────────────────────────────────────────────────────────────────────────────
# Report item #1 — repo.py calls c.fetchone()/fetchall() on a connection that
# doesn't have those methods (psycopg3 AsyncConnection only has .execute(),
# which returns a cursor).
# ─────────────────────────────────────────────────────────────────────────────

class _FakeCursor:
    """Mimics the object psycopg3's Connection.execute() actually returns."""

    def __init__(self, rows):
        self._rows = rows

    async def fetchone(self):
        return self._rows[0] if self._rows else None

    async def fetchall(self):
        return self._rows


def test_asyncconnection_has_no_fetchone_or_fetchall():
    """
    [GREEN] Sanity check on the library itself — proves the premise of #1.
    If this ever fails, psycopg's API has changed and the bug report should
    be re-evaluated.
    """
    assert not hasattr(psycopg.AsyncConnection, "fetchone")
    assert not hasattr(psycopg.AsyncConnection, "fetchall")
    assert hasattr(psycopg.AsyncConnection, "execute")


@pytest.mark.asyncio
async def test_create_case_uses_real_psycopg_connection_api(monkeypatch):
    """
    [RED until #1 is fixed]

    Builds a mock connection with `spec=psycopg.AsyncConnection`, so calling
    any method the real class doesn't have (e.g. `.fetchone()` directly on
    the connection) raises AttributeError — exactly what happens against a
    real Postgres connection today.

    This test currently fails with:
        AttributeError: 'coroutine' object has no attribute 'fetchone'
        (or similar, depending on mock internals)

    It will pass once repo.py is changed to:
        cur = await c.execute(sql, params)
        row = await cur.fetchone()
    """
    fake_conn = AsyncMock(spec=psycopg.AsyncConnection)
    fake_row = (datetime.now(timezone.utc), datetime.now(timezone.utc))
    fake_conn.execute.return_value = _FakeCursor(rows=[fake_row])

    @asynccontextmanager
    async def _fake_conn_cm():
        yield fake_conn

    monkeypatch.setattr(repo, "_conn", _fake_conn_cm)

    case = await repo.create_case(
        slack_channel="C_TEST",
        slack_ts="123.456",
        reporter_slack_id="U_TEST",
    )

    assert case.slack_channel == "C_TEST"
    assert case.created_at == fake_row[0]
    assert case.updated_at == fake_row[1]


# ─────────────────────────────────────────────────────────────────────────────
# Report item #2 — confidence is never used by the reconciler; there is no
# "thin evidence" / "low confidence" silence state.
# ─────────────────────────────────────────────────────────────────────────────

def test_thin_evidence_should_not_return_a_confident_verdict():
    """
    [RED until #18 is implemented]

    Spec, from Sentinel_Winning_Edition_Bible.md §8: "When evidence is thin
    or agents disagree hard, Sentinel does not manufacture a confidence
    number." A single low-signal claim should not resolve to a definitive
    CLEAR/REVIEW/FRAUD_LIKELY verdict.

    Currently fails because reconcile() never inspects claim.confidence or
    claim count, and there is no NEEDS_INFO/UNCERTAIN verdict category.
    """
    from sentinel.claims import Claim
    from sentinel.pipeline import run_case

    thin_claims = [
        Claim(
            field="domain_age_days",
            value=50,
            confidence=0.99,
            source_pointer="whois",
            agent="threat_intel",
        )
    ]
    verdict = run_case(thin_claims)

    assert verdict.verdict not in ("CLEAR", "FRAUD_LIKELY", "REVIEW"), (
        "Single-claim evidence resolved to a confident verdict "
        f"({verdict.verdict!r}) instead of signaling uncertainty."
    )


def test_low_confidence_claims_should_not_return_a_confident_verdict():
    """
    [RED until #18 is implemented]

    Two claims agree on a value, but both agents report low confidence
    (avg < 0.3). Per the same spec, this should not be silently resolved.
    """
    from sentinel.claims import Claim
    from sentinel.pipeline import run_case

    low_conf_claims = [
        Claim(field="visual_total", value=500.0, confidence=0.2, source_pointer="page1", agent="vision"),
        Claim(field="structured_total", value=500.0, confidence=0.1, source_pointer="page2", agent="finance"),
    ]
    verdict = run_case(low_conf_claims)

    assert verdict.verdict not in ("CLEAR", "FRAUD_LIKELY", "REVIEW"), (
        "Low-confidence agreeing claims resolved to a confident verdict "
        f"({verdict.verdict!r}) instead of signaling uncertainty."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Report item #3 — invalid CORS config (wildcard origin + credentials).
# ─────────────────────────────────────────────────────────────────────────────

def test_cors_does_not_combine_wildcard_origin_with_credentials():
    """
    [RED until #3 is fixed]

    allow_origins=["*"] with allow_credentials=True is an invalid/unsafe
    combination. Either origins must be an explicit list, or credentials
    must be off.
    """
    from sentinel.gateway import api

    cors_middlewares = [
        m for m in api.user_middleware if "CORSMiddleware" in str(m.cls)
    ]
    assert cors_middlewares, "CORSMiddleware not found on the app"

    options = cors_middlewares[0].kwargs
    allow_origins = options.get("allow_origins", [])
    allow_credentials = options.get("allow_credentials", False)

    if allow_credentials:
        assert allow_origins != ["*"], (
            "CORS allows credentials with a wildcard origin — "
            "use an explicit origin allow-list instead."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Report item #4 — aiohttp is required transitively but missing from
# requirements.txt.
# ─────────────────────────────────────────────────────────────────────────────

def test_requirements_txt_declares_aiohttp():
    """
    [RED until #4 is fixed]

    slack_bolt.async_app (imported by gateway.py's AsyncSlackRequestHandler)
    requires aiohttp. It must be declared explicitly rather than relying on
    it being present by accident.
    """
    with open("requirements.txt") as f:
        contents = f.read().lower()
    assert "aiohttp" in contents, (
        "aiohttp is required transitively by slack-bolt's async app but "
        "is not pinned in requirements.txt"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Report item #5 — Slack env vars silently default to empty strings instead
# of failing fast.
# ─────────────────────────────────────────────────────────────────────────────

def test_slack_app_fails_fast_on_missing_credentials(monkeypatch):
    """
    [RED until #5 is fixed]

    Importing slack_app with no SLACK_BOT_TOKEN / SLACK_SIGNING_SECRET set
    should raise clearly at startup, not silently construct an app with
    empty-string credentials.
    """
    import sys

    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
    sys.modules.pop("sentinel.slack_app", None)

    with pytest.raises(Exception):
        import sentinel.slack_app  # noqa: F401