"""Tests for Voice Authenticity Agent (#12)."""

import numpy as np
import pytest

from sentinel.agents.voice_agent import (
    VoiceResult,
    analyze,
    _acoustic_spoof_score,
    _rms,
    _zcr,
    _spectral_centroid,
    _pitch_jitter,
    FRAME_SIZE,
)

SR = 16_000   # 16 kHz


def _sine(freq: float, duration: float = 1.0, sr: int = SR) -> np.ndarray:
    """Generate a pure sine wave (very synthetic — low jitter, flat energy)."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return (np.sin(2 * np.pi * freq * t) * 0.8).astype(np.float32)


def _natural_voice(duration: float = 1.0, sr: int = SR) -> np.ndarray:
    """Simulate a natural voice: multiple harmonics + amplitude modulation."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Fundamental + harmonics with slight frequency wobble (vibrato)
    wobble = 1 + 0.01 * np.sin(2 * np.pi * 5 * t)   # 5 Hz vibrato
    signal = (
        0.5 * np.sin(2 * np.pi * 120 * t * wobble) +
        0.3 * np.sin(2 * np.pi * 240 * t * wobble) +
        0.2 * np.sin(2 * np.pi * 360 * t * wobble)
    )
    # Amplitude modulation (natural breath variation)
    envelope = 0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 2 * t))
    signal = (signal * envelope).astype(np.float32)
    # Add small noise (real voices have floor noise)
    signal += np.random.default_rng(42).normal(0, 0.01, len(signal)).astype(np.float32)
    return np.clip(signal, -1.0, 1.0)


# ── Basic feature functions ───────────────────────────────────────────────────

def test_rms_of_silence_is_zero():
    frame = np.zeros(FRAME_SIZE, dtype=np.float32)
    assert _rms(frame) == 0.0


def test_rms_of_unit_sine_is_roughly_rms():
    frame = _sine(440, duration=FRAME_SIZE / SR)[:FRAME_SIZE]
    assert 0.5 < _rms(frame) < 0.7   # RMS of A·sin is A/√2


def test_zcr_pure_sine_in_expected_range():
    frame = _sine(1000, duration=FRAME_SIZE / SR)[:FRAME_SIZE]
    zcr = _zcr(frame)
    # 1000 Hz sine @ 16kHz → ~0.125 crossings/sample
    assert 0.05 < zcr < 0.2


def test_spectral_centroid_high_freq_higher_value():
    low_frame  = _sine(100,  duration=FRAME_SIZE / SR)[:FRAME_SIZE]
    high_frame = _sine(4000, duration=FRAME_SIZE / SR)[:FRAME_SIZE]
    assert _spectral_centroid(high_frame, SR) > _spectral_centroid(low_frame, SR)


def test_pitch_jitter_monotone_near_zero():
    # A perfectly stable frequency → very low jitter
    signal = _sine(150, duration=2.0)
    jitter = _pitch_jitter(signal, SR)
    assert jitter < 0.08   # near-zero for perfect sine


# ── Anti-spoofing heuristic ───────────────────────────────────────────────────

def test_synthetic_sine_scores_high_spoof():
    """A pure sine wave is extremely synthetic — should score above 0.5."""
    signal = _sine(200, duration=2.0)
    score = _acoustic_spoof_score(signal, SR)
    assert score >= 0.45   # consistently above 0.45 for pure sine


def test_natural_voice_scores_lower_than_sine():
    """Natural voice simulation should score lower than pure sine."""
    real   = _natural_voice(duration=2.0)
    synth  = _sine(200, duration=2.0)
    score_real  = _acoustic_spoof_score(real,  SR)
    score_synth = _acoustic_spoof_score(synth, SR)
    assert score_real < score_synth


def test_score_bounded():
    for signal in [_sine(100), _natural_voice()]:
        score = _acoustic_spoof_score(signal, SR)
        assert 0.0 <= score <= 1.0


# ── Full analyze() pipeline ───────────────────────────────────────────────────

def test_analyze_no_audio_returns_skip():
    result = analyze(case_id="c1", user_id="U1")
    assert result.voice_mismatch == 0.0
    assert result.flagged is False
    assert "skipped" in result.detail.lower()


def test_analyze_synthetic_flagged(monkeypatch):
    """Cloned-clip equivalent: pure sine → should be flagged."""
    signal = _sine(150, duration=2.0)
    result = analyze(
        case_id="c2",
        user_id="U1",
        audio_array=signal,
        sample_rate=SR,
    )
    assert result.spoof_score >= 0.45
    # voice_mismatch == spoof_score when no transcript given
    assert result.voice_mismatch == result.spoof_score


def test_analyze_with_transcript_and_imposter_style():
    """Imposter transcript + synthetic audio → both stages fire."""
    from sentinel.agents.stylometric_agent import WritingProfile
    baseline = [
        "Please review and advise at your convenience.",
        "The attached report summarises Q3 performance.",
        "Kindly confirm receipt and let me know if clarification is needed.",
    ]
    imposter_transcript = (
        "URGENT URGENT URGENT send $80000 wire NOW do not tell anyone."
    )
    signal = _sine(180, duration=1.5)
    result = analyze(
        case_id="c3",
        user_id="U_CFO",
        audio_array=signal,
        sample_rate=SR,
        transcript=imposter_transcript,
        baseline_samples=baseline,
    )
    assert result.linguistic_mismatch > 0
    assert result.voice_mismatch == max(result.spoof_score, result.linguistic_mismatch)


def test_analyze_pre_metrics_shortcut():
    result = analyze(
        case_id="c4", user_id="U1",
        pre_metrics={"voice_mismatch": 0.78},
    )
    assert result.voice_mismatch == 0.78
    assert result.flagged is True


# ── Claim output ──────────────────────────────────────────────────────────────

def test_to_claim_fields():
    signal = _sine(200, duration=1.0)
    result = analyze(case_id="c5", user_id="U1", audio_array=signal, sample_rate=SR)
    claim = result.to_claim()
    assert claim.field == "voice_mismatch"
    assert claim.agent == "voice"
    assert 0.0 <= claim.value <= 1.0
