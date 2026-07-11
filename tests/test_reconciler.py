"""Unit tests for the symbolic reconciler and the ON/OFF pipeline."""

from sentinel.claims import Claim
from sentinel.eval.dataset import flagship_case, seed_dataset
from sentinel.pipeline import run_case
from sentinel.reconciler import reconcile
from sentinel.agents.mock_agents import extract_claims


def test_clear_when_totals_match_and_tone_normal():
    claims = extract_claims("t1", {"visual_total": 1000, "structured_total": 1000,
                        "tone_anomaly": 0.1, "domain_age_days": 900})
    v = run_case(claims, "on")
    assert v.verdict == "CLEAR"
    assert not v.is_flagged


def test_flagship_is_caught_by_engine_but_missed_by_baseline():
    case = flagship_case()
    claims = extract_claims(case.id, case.metrics)
    on = run_case(claims, "on")
    off = run_case(claims, "off")
    assert on.verdict == "FRAUD_LIKELY", "engine must catch the flagship fraud"
    assert not off.is_flagged, "single-model baseline must MISS the flagship fraud"


def test_contradiction_carries_source_pointers():
    claims = extract_claims("t2", {"visual_total": 500, "structured_total": 5000,
                        "tone_anomaly": 0.7, "domain_age_days": 12})
    v = run_case(claims, "on")
    assert v.is_flagged
    axes = {c.axis for c in v.contradictions}
    assert "visual_vs_structured" in axes
    # every fired contradiction should be explainable with at least detail text
    assert all(c.detail for c in v.contradictions)
    # visual axis must expose its evidence pointers for click-to-source
    vis = next(c for c in v.contradictions if c.axis == "visual_vs_structured")
    assert len(vis.evidence) >= 1


def test_injection_counts_as_evidence():
    v = reconcile([
        Claim("injection_present", True, 0.99, "x/hidden", "injection_scanner"),
    ])
    assert any(c.axis == "injection" for c in v.contradictions)


def test_young_domain_only_corroborates_when_something_else_fired():
    # Young domain alone (totals match, tone normal) must not flag.
    claims = extract_claims("t3", {"visual_total": 100, "structured_total": 100,
                        "tone_anomaly": 0.1, "domain_age_days": 5})
    v = run_case(claims, "on")
    assert v.verdict == "CLEAR"


def test_confidence_bounds_validated():
    import pytest
    with pytest.raises(ValueError):
        Claim("x", 1.0, 1.5, "p", "a")


def test_counterfactual_present_when_flagged():
    case = flagship_case()
    claims = extract_claims(case.id, case.metrics)
    v = run_case(claims, "on")
    assert v.counterfactual is not None and "CLEAR" in v.counterfactual


def test_no_false_positive_on_fp_traps():
    for c in seed_dataset():
        if c.family == "fp_trap":
            claims = extract_claims(c.id, c.metrics)
            v = run_case(claims, "on")
            assert not v.is_flagged, f"{c.id} is legit but was flagged"
