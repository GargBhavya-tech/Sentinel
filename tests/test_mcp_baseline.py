"""Tests for MCP baseline retrieval and its effect on the stylometric agent.

Under the test token (conftest sets a placeholder), fetch_writing_baseline
falls back to the curated seed. With that baseline in hand, an urgent impostor
message must register a non-trivial tone_anomaly — the signal that was dead in
the live path before baselines were wired in.
"""

from __future__ import annotations

from sentinel.mcp_baseline import fetch_writing_baseline, curated_baseline
from sentinel.agents import stylometric_agent
from sentinel.agents.harvest import harvest_claims


async def test_fetch_baseline_falls_back_to_curated_for_known_user():
    samples = await fetch_writing_baseline("U_CEO")
    assert samples == curated_baseline("U_CEO")
    assert len(samples) >= 2


async def test_fetch_baseline_empty_for_unknown_user():
    assert await fetch_writing_baseline("U_NOBODY_12345") == []


async def test_baseline_makes_tone_anomaly_live():
    baseline = await fetch_writing_baseline("U_CEO")
    impostor = (
        "URGENT!! wire the funds NOW. transfer $5,000,000 immediately, "
        "keep this strictly confidential, do not tell anyone. do it today."
    )
    res = stylometric_agent.analyze(
        "case-1", "U_CEO", impostor, baseline_samples=baseline
    )
    # The impostor message deviates from the calm baseline -> anomaly registers
    # and the claim survives the harvest seam.
    assert res.tone_anomaly > 0.0
    claims = harvest_claims(res)
    assert [c.field for c in claims] == ["tone_anomaly"]
