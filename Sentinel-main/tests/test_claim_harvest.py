"""Integration test for the agent -> reconciler seam.

This is the test that would have caught the `to_claim` vs `to_claims` bug:
Voice, Stylometric, and Policy agents expose `to_claim()` (singular) and were
silently dropped by both workers, disabling the voice + tone contradiction
axes. These tests assert the seam preserves EVERY agent's output and that the
flagship 3-way scenario fires all three axes end to end.
"""

from __future__ import annotations

from sentinel.agents.harvest import harvest_claims
from sentinel.agents import voice_agent, policy_agent, threat_intel_agent
from sentinel.demo_fixtures import demo_claims
from sentinel.reconciler import reconcile


# ── harvest handles both claim shapes ──────────────────────────────────────────

def test_harvest_collects_singular_to_claim_from_voice():
    # A synthetic clone-like signal via pre_metrics (deterministic).
    res = voice_agent.analyze("case-1", "U_CEO", pre_metrics={"voice_mismatch": 0.9})
    claims = harvest_claims(res)
    assert [c.field for c in claims] == ["voice_mismatch"]
    assert claims[0].value == 0.9


def test_harvest_collects_singular_to_claim_from_policy():
    res = policy_agent.analyze("case-1", 1_450_000.0, ["employee"])
    claims = harvest_claims(res)
    assert [c.field for c in claims] == ["policy_violation"]
    assert claims[0].value is True  # unauthorised for an ULTRA-tier request


def test_harvest_collects_plural_to_claims_from_threat_intel():
    threat_intel_agent.seed_cache("evilpayments-inc.com", {
        "domain_age_days": 12, "vt_malicious": 8, "vt_suspicious": 3,
    })
    res = threat_intel_agent.analyze("case-1", "evilpayments-inc.com")
    fields = {c.field for c in harvest_claims(res)}
    assert "domain_age_days" in fields and "threat_risk" in fields


def test_harvest_is_safe_on_none_and_exceptions():
    assert harvest_claims(None) == []
    assert harvest_claims(ValueError("boom")) == []


# ── flagship 3-way scenario fires all three axes ───────────────────────────────

def test_flagship_demo_fires_three_axes():
    claims = demo_claims("case-flagship")
    verdict = reconcile(claims)
    axes = {c.axis for c in verdict.contradictions}
    assert verdict.verdict == "FRAUD_LIKELY"
    assert "visual_vs_structured" in axes
    assert "tone_vs_baseline" in axes
    assert "voice_vs_baseline" in axes


# ── regression: unknown domain age must NOT force fraud ────────────────────────

def test_unknown_domain_age_does_not_emit_claim():
    # No VT key, uncached domain -> domain_age_days is None -> NO claim emitted
    # (previously emitted -1, which the reconciler read as "registered -1 days
    # ago" and floored risk to 0.90).
    threat_intel_agent.clear_cache()
    res = threat_intel_agent.analyze("case-1", "totally-unknown-domain-xyz.com")
    fields = {c.field for c in harvest_claims(res)}
    assert "domain_age_days" not in fields


def test_unknown_domain_age_alone_is_not_fraud():
    # A lone threat_risk=0 claim (unknown domain) must reconcile to CLEAR.
    threat_intel_agent.clear_cache()
    res = threat_intel_agent.analyze("case-1", "totally-unknown-domain-xyz.com")
    verdict = reconcile(harvest_claims(res))
    assert verdict.verdict == "CLEAR"
