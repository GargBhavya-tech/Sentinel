"""Tests for the self-writing detection rules system (build-map ticket #26)."""

from __future__ import annotations

import pytest

from sentinel.claims import Claim, Verdict, Contradiction
from sentinel.rules.schema import Rule
from sentinel.rules.engine import match_rules
from sentinel.rules.synthesizer import synthesize_rule


# ── Schema / fingerprint ───────────────────────────────────────────────────────

def test_rule_fingerprint_is_deterministic():
    r = Rule(ratio_threshold=3.5, tone_anomaly_threshold=0.6)
    assert r.fingerprint == r.fingerprint  # same object
    r2 = Rule(ratio_threshold=3.5, tone_anomaly_threshold=0.6)
    assert r.fingerprint == r2.fingerprint  # same conditions → same fingerprint


def test_rule_fingerprint_changes_with_conditions():
    r1 = Rule(ratio_threshold=3.5)
    r2 = Rule(ratio_threshold=4.0)
    assert r1.fingerprint != r2.fingerprint


def test_rule_roundtrip_to_from_dict():
    r = Rule(
        source_case_id="case-123",
        ratio_threshold=2.5,
        tone_anomaly_threshold=0.7,
        description="Test rule",
    )
    d = r.to_dict()
    r2 = Rule.from_dict(d)
    assert r2.rule_id == r.rule_id
    assert r2.ratio_threshold == r.ratio_threshold
    assert r2.tone_anomaly_threshold == r.tone_anomaly_threshold
    assert r2.description == r.description


# ── Engine ────────────────────────────────────────────────────────────────────

def _make_claims(visual=1000, structured=1000, tone=0.1, domain_age=500):
    return [
        Claim(field="visual_total", value=visual, confidence=1.0, source_pointer="", agent="vision"),
        Claim(field="structured_total", value=structured, confidence=1.0, source_pointer="", agent="finance"),
        Claim(field="tone_anomaly", value=tone, confidence=1.0, source_pointer="", agent="stylometric"),
        Claim(field="domain_age_days", value=domain_age, confidence=1.0, source_pointer="", agent="threat_intel"),
    ]


def test_enforced_rule_fires_on_matching_claims():
    rule = Rule(
        ratio_threshold=3.0,  # fires if ratio >= 3.0
        status="enforced",
        verdict="FRAUD_LIKELY",
    )
    # visual=5000, structured=1000 → ratio=5 → matches
    claims = _make_claims(visual=5000, structured=1000)
    matched = match_rules(claims, [rule])
    assert matched is not None
    assert matched.verdict == "FRAUD_LIKELY"


def test_enforced_rule_does_not_fire_when_below_threshold():
    rule = Rule(ratio_threshold=10.0, status="enforced")
    # ratio=1.5 — doesn't meet threshold
    claims = _make_claims(visual=1500, structured=1000)
    matched = match_rules(claims, [rule])
    assert matched is None


def test_shadow_rule_never_returned_even_when_it_fires():
    rule = Rule(ratio_threshold=3.0, status="shadow")
    claims = _make_claims(visual=5000, structured=1000)
    matched = match_rules(claims, [rule])
    assert matched is None  # shadow → always returns None


def test_multiple_conditions_must_all_be_met():
    rule = Rule(
        ratio_threshold=3.0,
        tone_anomaly_threshold=0.7,
        status="enforced",
    )
    # ratio fires but tone doesn't
    claims = _make_claims(visual=5000, structured=1000, tone=0.3)
    assert match_rules(claims, [rule]) is None

    # both fire
    claims = _make_claims(visual=5000, structured=1000, tone=0.8)
    assert match_rules(claims, [rule]) is not None


def test_injection_condition():
    rule = Rule(injection_present=True, status="enforced")
    claims = [
        Claim(field="injection_present", value=True, confidence=1.0, source_pointer="", agent="scanner"),
    ]
    assert match_rules(claims, [rule]) is not None

    claims_no_injection = [
        Claim(field="injection_present", value=False, confidence=1.0, source_pointer="", agent="scanner"),
    ]
    assert match_rules(claims_no_injection, [rule]) is None


def test_domain_age_condition():
    rule = Rule(domain_age_days_max=10, status="enforced")
    # domain age 5 < 10 → fires
    claims = _make_claims(domain_age=5)
    assert match_rules(claims, [rule]) is not None
    # domain age 20 >= 10 → doesn't fire
    claims2 = _make_claims(domain_age=20)
    assert match_rules(claims2, [rule]) is None


# ── Synthesizer ───────────────────────────────────────────────────────────────

def _fraud_verdict(axes=("visual_vs_structured",)):
    contradictions = [
        Contradiction(axis=ax, detail="test", weight=0.8, evidence=[])
        for ax in axes
    ]
    return Verdict(risk=0.9, verdict="FRAUD_LIKELY", contradictions=contradictions, counterfactual=None)


def test_synthesize_rule_from_ratio_fraud():
    claims = _make_claims(visual=5000, structured=1000)
    verdict = _fraud_verdict(axes=["visual_vs_structured"])
    rule = synthesize_rule("case-abc", verdict, claims)
    assert rule is not None
    assert rule.status == "shadow"
    assert rule.ratio_threshold is not None
    # threshold = observed_ratio * 0.85 = 5.0 * 0.85 = 4.25
    assert rule.ratio_threshold == pytest.approx(4.25, abs=0.01)


def test_synthesize_rule_from_tone_fraud():
    claims = _make_claims(tone=0.85)
    verdict = _fraud_verdict(axes=["tone_vs_baseline"])
    rule = synthesize_rule("case-def", verdict, claims)
    assert rule is not None
    assert rule.tone_anomaly_threshold is not None
    assert rule.tone_anomaly_threshold == pytest.approx(0.85 * 0.9, abs=0.001)


def test_synthesize_rule_returns_none_when_not_fraud():
    claims = _make_claims()
    verdict = Verdict(risk=0.1, verdict="CLEAR", contradictions=[], counterfactual=None)
    rule = synthesize_rule("case-clear", verdict, claims)
    assert rule is None


def test_synthesize_rule_fingerprint_in_dict():
    claims = _make_claims(visual=5000, structured=1000)
    verdict = _fraud_verdict()
    rule = synthesize_rule("case-fp", verdict, claims)
    assert rule is not None
    d = rule.to_dict()
    assert "fingerprint" in d
    assert len(d["fingerprint"]) == 64  # SHA-256 hex


def test_pipeline_enforced_rule_short_circuits():
    """An enforced rule must short-circuit the full contradiction engine."""
    from sentinel.pipeline import run_case
    from sentinel.rules.schema import Rule

    enforced = Rule(
        ratio_threshold=3.0,
        status="enforced",
        verdict="FRAUD_LIKELY",
        description="Test enforced rule",
    )
    claims = _make_claims(visual=8000, structured=1000)  # ratio=8 → fires
    verdict = run_case(claims, contradiction_engine="on", enforced_rules=[enforced])
    assert verdict.verdict == "FRAUD_LIKELY"
    assert "Matched enforced rule" in (verdict.counterfactual or "")
