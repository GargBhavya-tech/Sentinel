"""Tests for Stylometric Agent (#11)."""

import numpy as np
import pytest

from sentinel.agents.stylometric_agent import (
    ANOMALY_THRESHOLD,
    WritingProfile,
    analyze,
    _cosine_similarity,
    _extract_features,
)

# ── Curated demo pair ─────────────────────────────────────────────────────────
# Realistic CFO baseline: formal, precise, low urgency
_BASELINE_SAMPLES = [
    "Please find attached the Q3 budget reconciliation. Let me know if you need clarification.",
    "I have reviewed the vendor proposal. The figures look reasonable given current rates.",
    "Following up on last week's discussion — the approval matrix has been updated accordingly.",
    "Could you please share the revised cost breakdown by end of day Thursday? Thank you.",
    "The compliance team has signed off. We can proceed with the wire once legal confirms.",
]

# Attacker impersonating CFO: urgent, informal, imperative
_IMPOSTER_TEXT = (
    "URGENT: Wire $87,500 to account 1234-5678 NOW. Do not discuss with anyone. "
    "This is a confidential executive request. Complete immediately before end of business."
)

# Real CFO message (should match baseline)
_REAL_TEXT = (
    "Hi team, please process the attached invoice after confirming with procurement. "
    "Standard approval applies. Thank you."
)


# ── Feature extraction ────────────────────────────────────────────────────────

def test_feature_vector_is_finite():
    vec = _extract_features(_BASELINE_SAMPLES[0])
    assert np.all(np.isfinite(vec))


def test_feature_vector_not_all_zeros():
    vec = _extract_features("Hello, world! This is a test sentence.")
    assert vec.sum() > 0


def test_empty_text_returns_zero_vector():
    vec = _extract_features("")
    assert np.all(vec == 0)


def test_different_texts_different_vectors():
    v1 = _extract_features(_BASELINE_SAMPLES[0])
    v2 = _extract_features(_IMPOSTER_TEXT)
    assert not np.allclose(v1, v2)


# ── Cosine similarity ─────────────────────────────────────────────────────────

def test_identical_vectors_similarity_one():
    v = _extract_features(_BASELINE_SAMPLES[0])
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-5


def test_zero_vector_similarity_zero():
    v = _extract_features("Some text")
    z = np.zeros_like(v)
    assert _cosine_similarity(v, z) == 0.0


# ── WritingProfile ────────────────────────────────────────────────────────────

def test_profile_build_succeeds():
    profile = WritingProfile.build("U123", _BASELINE_SAMPLES)
    assert profile.sample_count == len(_BASELINE_SAMPLES)
    assert profile.mean_vector.shape == _extract_features(_BASELINE_SAMPLES[0]).shape


def test_profile_requires_at_least_one_sample():
    with pytest.raises(ValueError, match="Need ≥ 1 sample"):
        WritingProfile.build("U123", [])


# ── Core demo: imposter flagged, real CFO not flagged ────────────────────────

def test_imposter_is_flagged():
    """The headline demo: cloned CFO voice flagged as anomalous."""
    result = analyze(
        case_id="case-demo",
        user_id="U_CFO",
        target_text=_IMPOSTER_TEXT,
        baseline_samples=_BASELINE_SAMPLES,
    )
    assert result.flagged is True
    assert result.tone_anomaly >= ANOMALY_THRESHOLD


def test_real_cfo_message_not_flagged():
    """Real CFO message should stay within the normal range."""
    result = analyze(
        case_id="case-demo",
        user_id="U_CFO",
        target_text=_REAL_TEXT,
        baseline_samples=_BASELINE_SAMPLES,
    )
    assert result.flagged is False
    assert result.tone_anomaly < ANOMALY_THRESHOLD


def test_alignment_imposter_lower_than_real():
    """Imposter must have lower baseline alignment than real author."""
    r_real = analyze("c1", "U_CFO", _REAL_TEXT, baseline_samples=_BASELINE_SAMPLES)
    r_imp  = analyze("c2", "U_CFO", _IMPOSTER_TEXT, baseline_samples=_BASELINE_SAMPLES)
    assert r_real.alignment > r_imp.alignment


# ── No baseline path ──────────────────────────────────────────────────────────

def test_no_baseline_returns_neutral():
    result = analyze(
        case_id="case-x",
        user_id="U_UNKNOWN",
        target_text="Some text",
    )
    assert result.flagged is False
    assert result.tone_anomaly == 0.0


# ── pre-built profile path ────────────────────────────────────────────────────

def test_pre_built_profile_used():
    profile = WritingProfile.build("U_CFO", _BASELINE_SAMPLES)
    result = analyze(
        case_id="case-y",
        user_id="U_CFO",
        target_text=_IMPOSTER_TEXT,
        baseline_profile=profile,
    )
    assert result.flagged is True


# ── Claim output ──────────────────────────────────────────────────────────────

def test_to_claim_field_and_agent():
    result = analyze("c3", "U", _IMPOSTER_TEXT, baseline_samples=_BASELINE_SAMPLES)
    claim = result.to_claim()
    assert claim.field == "tone_anomaly"
    assert claim.agent == "stylometric"
    assert 0.0 <= claim.value <= 1.0


def test_claim_confidence_is_reasonable():
    result = analyze("c4", "U", _IMPOSTER_TEXT, baseline_samples=_BASELINE_SAMPLES)
    claim = result.to_claim()
    assert 0.0 < claim.confidence <= 1.0
