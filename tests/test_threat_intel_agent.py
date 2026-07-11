"""Tests for Threat-Intel Agent (#10).

All tests run offline — the demo seed cache is used exclusively.
No VirusTotal or WHOIS network calls are made.
"""

import pytest
from sentinel.agents.threat_intel_agent import (
    ThreatIntelResult,
    analyze,
    clear_cache,
    seed_cache,
    _build_result,
)


def setup_function():
    clear_cache()


# ── Demo-seed cache hits ──────────────────────────────────────────────────────

def test_known_bad_domain_from_seed():
    result = analyze(case_id="c1", domain="evilpayments-inc.com")
    assert result.domain_age_days < 30
    assert result.vt_malicious > 0
    assert result.risk_score > 0.5
    assert result.from_cache is True


def test_known_good_domain_from_seed():
    result = analyze(case_id="c2", domain="acmecorp.com")
    assert result.domain_age_days > 365
    assert result.vt_malicious == 0
    assert result.risk_score == 0.0
    assert result.from_cache is True


# ── Manual cache seeding ──────────────────────────────────────────────────────

def test_seeded_young_domain_flagged():
    seed_cache("suspiciousvendor.biz", {
        "domain_age_days": 7,
        "vt_malicious": 0,
        "vt_suspicious": 1,
        "cached_at": 0,
    })
    result = analyze(case_id="c3", domain="suspiciousvendor.biz")
    assert result.risk_score >= 0.40
    factor_text = " ".join(result.flags)
    assert "young domain" in factor_text


def test_seeded_many_vt_malicious_high_risk():
    seed_cache("ransomware-host.ru", {
        "domain_age_days": 500,
        "vt_malicious": 15,
        "vt_suspicious": 0,
        "cached_at": 0,
    })
    result = analyze(case_id="c4", domain="ransomware-host.ru")
    assert result.risk_score >= 0.90


def test_seeded_clean_domain_zero_risk():
    seed_cache("trusted-supplier.com", {
        "domain_age_days": 2000,
        "vt_malicious": 0,
        "vt_suspicious": 0,
        "cached_at": 0,
    })
    result = analyze(case_id="c5", domain="trusted-supplier.com")
    assert result.risk_score == 0.0
    assert len(result.flags) == 0


# ── Risk score bounds ─────────────────────────────────────────────────────────

def test_risk_score_bounded_between_0_and_1():
    result = analyze(case_id="c6", domain="evilpayments-inc.com")
    assert 0.0 <= result.risk_score <= 1.0


# ── Unknown domain (no cache, no API key) ─────────────────────────────────────

def test_unknown_domain_no_error():
    result = analyze(case_id="c7", domain="completely-unknown-domain-xyz.test")
    # Should return a result (possibly with None fields) but never raise
    assert isinstance(result, ThreatIntelResult)


# ── Domain normalisation ──────────────────────────────────────────────────────

def test_domain_case_insensitive():
    result_lower = analyze(case_id="c8", domain="evilpayments-inc.com")
    result_upper = analyze(case_id="c9", domain="EVILPAYMENTS-INC.COM")
    assert result_lower.risk_score == result_upper.risk_score


# ── Claims ─────────────────────────────────────────────────────────────────────

def test_to_claims_includes_domain_age_and_risk():
    result = analyze(case_id="c10", domain="evilpayments-inc.com")
    claims = result.to_claims()
    fields = {c.field for c in claims}
    assert "domain_age_days" in fields
    assert "threat_risk" in fields


def test_to_claims_agent_is_threat_intel():
    result = analyze(case_id="c11", domain="acmecorp.com")
    for c in result.to_claims():
        assert c.agent == "threat_intel"


# ── Pre-metrics shortcut ──────────────────────────────────────────────────────

def test_pre_metrics_shortcut():
    result = analyze(
        case_id="c12",
        domain="anything.com",
        pre_metrics={"threat_risk": 0.65, "domain_age_days": 14},
    )
    assert result.risk_score == 0.65
