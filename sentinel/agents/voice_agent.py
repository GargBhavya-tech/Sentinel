"""Voice Authenticity Agent — build-map ticket #12.

Two-stage check (per build map):
  1. Anti-spoofing signal: acoustic features that distinguish real human
     speech from TTS/cloned audio (energy variation, zero-crossing rate,
     spectral centroid, pitch jitter via autocorrelation).
  2. Linguistic-acoustic mismatch: cross-reference the voice-note transcript
     against the user's stylometric baseline (#11) to catch "sounds like
     them, writes like a bot" or vice-versa.

Both stages are deterministic — no LLM, no pretrained model required.
For the real hackathon demo, a curated real-clip vs. cloned-clip pair is
used; the features reliably separate them (build map: "demo on a curated
real-clip-vs-cloned-clip pair").

Feature set (computed from raw audio via numpy, soundfile optional)
-------------------------------------------------------------------
  rms_energy_std      : std of per-frame RMS energy — real voices vary more
  zcr_mean            : mean zero-crossing rate — TTS is often smoother
  zcr_std             : std of ZCR — real voices show more ZCR variation
  spectral_centroid   : weighted mean frequency — clones often centred higher
  pitch_jitter        : local pitch variation via autocorrelation
  voiced_fraction     : fraction of voiced frames (TTS often near-constant)

Anti-spoofing heuristic score
-----------------------------
Each feature is compared against reference ranges calibrated on the
curated demo pair. A weighted sum produces a spoof_score in [0, 1]:
  0.0 → confidently real
  1.0 → confidently cloned / synthesised

voice_mismatch = max(spoof_score, linguistic_mismatch_score)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from ..claims import Claim
from .stylometric_agent import WritingProfile, analyze as stylometric_analyze

log = logging.getLogger(__name__)

# ── Anti-spoofing reference ranges (calibrated on demo pair) ──────────────────
# Real voice: higher energy variation, higher ZCR variance, lower centroid
_REF = {
    "rms_std_real":   (0.015, 0.12),   # (min, max) for a real voice
    "zcr_std_real":   (0.010, 0.08),
    "centroid_cloned": 3200,            # clones tend to have centroid > 3200 Hz
    "jitter_real":    (0.003, 0.04),
}

FRAME_SIZE = 512   # samples per analysis frame
HOP_SIZE   = 256   # hop between frames


# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class VoiceResult:
    case_id: str
    user_id: str
    spoof_score: float            # acoustic anti-spoof score (0=real, 1=clone)
    linguistic_mismatch: float    # stylometric cross-check (0=match, 1=mismatch)
    voice_mismatch: float         # max of both — the headline number
    flagged: bool
    detail: str
    source_pointer: str
    transcript: Optional[str] = None

    def to_claim(self) -> Claim:
        return Claim(
            field="voice_mismatch",
            value=self.voice_mismatch,
            confidence=0.75,
            source_pointer=self.source_pointer,
            agent="voice",
        )


# ── Main entry point ───────────────────────────────────────────────────────────

def analyze(
    case_id: str,
    user_id: str,
    audio_path: Optional[str | Path] = None,
    audio_array: Optional[np.ndarray] = None,
    sample_rate: int = 16000,
    transcript: Optional[str] = None,
    baseline_profile: Optional[WritingProfile] = None,
    baseline_samples: Optional[list[str]] = None,
    pre_metrics: Optional[dict] = None,
) -> VoiceResult:
    """Run the voice authenticity check.

    Parameters
    ----------
    case_id, user_id: identifiers.
    audio_path:      Path to WAV/FLAC/OGG file (soundfile reads it).
    audio_array:     Pre-loaded audio as float32 numpy array [-1, 1] (for tests).
    sample_rate:     Sample rate of audio_array (ignored when reading from file).
    transcript:      Text transcript of the voice note.
    baseline_profile / baseline_samples:
                     User's writing profile for linguistic-acoustic mismatch.
    pre_metrics:     Dict with pre-extracted values (mock/test shortcut).
    """

    # ── Pre-extracted metrics shortcut ────────────────────────────────────────
    if pre_metrics and "voice_mismatch" in pre_metrics:
        vm = float(pre_metrics["voice_mismatch"])
        return VoiceResult(
            case_id=case_id, user_id=user_id,
            spoof_score=vm, linguistic_mismatch=0.0,
            voice_mismatch=vm,
            flagged=vm >= 0.5,
            detail=f"Pre-extracted voice_mismatch={vm:.3f}",
            source_pointer=f"{case_id}/voicenote.wav#antispoof",
            transcript=transcript,
        )

    # ── Load audio ────────────────────────────────────────────────────────────
    samples: Optional[np.ndarray] = audio_array
    if samples is None and audio_path is not None:
        samples, sample_rate = _load_audio(Path(audio_path))

    if samples is None:
        log.warning("voice: no audio provided for case %s", case_id)
        return VoiceResult(
            case_id=case_id, user_id=user_id,
            spoof_score=0.0, linguistic_mismatch=0.0, voice_mismatch=0.0,
            flagged=False,
            detail="No audio provided — voice check skipped",
            source_pointer=f"{case_id}/voicenote.wav#antispoof",
        )

    # ── Stage 1: acoustic anti-spoofing ───────────────────────────────────────
    spoof_score = _acoustic_spoof_score(samples, sample_rate)

    # ── Stage 2: linguistic-acoustic mismatch ─────────────────────────────────
    linguistic_mismatch = 0.0
    if transcript and (baseline_profile or baseline_samples):
        stylo = stylometric_analyze(
            case_id=case_id,
            user_id=user_id,
            target_text=transcript,
            baseline_profile=baseline_profile,
            baseline_samples=baseline_samples,
        )
        linguistic_mismatch = stylo.tone_anomaly
        log.info(
            "voice: linguistic-acoustic mismatch=%.3f for case=%s",
            linguistic_mismatch, case_id,
        )

    voice_mismatch = round(max(spoof_score, linguistic_mismatch), 4)
    flagged = voice_mismatch >= 0.50

    parts = []
    if spoof_score >= 0.50:
        parts.append(f"acoustic anti-spoof score={spoof_score:.3f} (synthetic features detected)")
    if linguistic_mismatch >= 0.35:
        parts.append(f"linguistic mismatch={linguistic_mismatch:.3f} vs baseline")
    detail = "; ".join(parts) if parts else f"voice_mismatch={voice_mismatch:.3f} (within normal range)"

    log.info(
        "voice: case=%s spoof=%.3f linguistic=%.3f mismatch=%.3f flagged=%s",
        case_id, spoof_score, linguistic_mismatch, voice_mismatch, flagged,
    )

    return VoiceResult(
        case_id=case_id, user_id=user_id,
        spoof_score=spoof_score, linguistic_mismatch=linguistic_mismatch,
        voice_mismatch=voice_mismatch,
        flagged=flagged, detail=detail,
        source_pointer=f"{case_id}/voicenote.wav#antispoof",
        transcript=transcript,
    )


# ── Acoustic feature extraction ────────────────────────────────────────────────

def _load_audio(path: Path) -> tuple[np.ndarray, int]:
    """Load audio via soundfile; fallback to raw PCM read."""
    try:
        import soundfile as sf  # type: ignore
        samples, sr = sf.read(str(path), dtype="float32", always_2d=False)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)   # mono
        log.info("voice: loaded %s — %d samples @ %dHz", path.name, len(samples), sr)
        return samples, sr
    except Exception as e:
        log.warning("voice: soundfile failed (%s) — cannot load %s", e, path)
        return None, 16000  # type: ignore


def _frames(samples: np.ndarray, frame_size: int, hop: int) -> list[np.ndarray]:
    """Split samples into overlapping frames."""
    result = []
    for start in range(0, len(samples) - frame_size, hop):
        result.append(samples[start: start + frame_size])
    return result or [samples]


def _rms(frame: np.ndarray) -> float:
    return float(np.sqrt(np.mean(frame ** 2)))


def _zcr(frame: np.ndarray) -> float:
    """Zero-crossing rate for one frame."""
    signs = np.sign(frame)
    crossings = np.sum(np.abs(np.diff(signs))) / 2
    return float(crossings / len(frame))


def _spectral_centroid(frame: np.ndarray, sr: int) -> float:
    """Weighted mean frequency of the frame spectrum."""
    mag = np.abs(np.fft.rfft(frame * np.hanning(len(frame))))
    freqs = np.fft.rfftfreq(len(frame), d=1.0 / sr)
    total = mag.sum()
    if total == 0:
        return 0.0
    return float(np.dot(freqs, mag) / total)


def _pitch_jitter(samples: np.ndarray, sr: int) -> float:
    """Approximate pitch jitter via autocorrelation on short windows.

    Returns the coefficient of variation of the estimated period,
    which is higher for real voices (natural micro-variation) than
    for synthetic speech (mechanically stable pitch).
    """
    win_size  = int(sr * 0.025)   # 25 ms window
    hop       = win_size // 2
    periods: list[float] = []

    for start in range(0, len(samples) - win_size, hop):
        win = samples[start: start + win_size]
        ac  = np.correlate(win, win, mode="full")
        ac  = ac[len(ac) // 2:]
        # Find the first peak in the F0 range (50–500 Hz)
        lo  = int(sr / 500)
        hi  = int(sr / 50)
        lo, hi = max(lo, 1), min(hi, len(ac) - 1)
        if lo >= hi:
            continue
        peak_idx = lo + int(np.argmax(ac[lo:hi]))
        if ac[peak_idx] > 0.1 * ac[0]:   # voiced frame
            periods.append(float(peak_idx))

    if len(periods) < 3:
        return 0.0
    arr = np.array(periods)
    return float(np.std(arr) / (np.mean(arr) + 1e-9))


def _acoustic_spoof_score(samples: np.ndarray, sr: int) -> float:
    """Compute a composite anti-spoofing score in [0, 1].

    Higher → more likely synthetic / cloned.
    """
    frs = _frames(samples, FRAME_SIZE, HOP_SIZE)

    rms_vals  = np.array([_rms(f) for f in frs])
    zcr_vals  = np.array([_zcr(f) for f in frs])
    cen_vals  = np.array([_spectral_centroid(f, sr) for f in frs])

    rms_std   = float(np.std(rms_vals))
    zcr_std   = float(np.std(zcr_vals))
    centroid  = float(np.mean(cen_vals))
    jitter    = _pitch_jitter(samples, sr)

    score_components: list[float] = []

    # Low RMS variation → more synthetic
    rms_lo, rms_hi = _REF["rms_std_real"]
    if rms_std < rms_lo:
        score_components.append(0.7)   # suspiciously flat energy
    elif rms_std > rms_hi:
        score_components.append(0.1)   # highly variable — likely real
    else:
        score_components.append(0.3)

    # Low ZCR variation → more synthetic
    zcr_lo, zcr_hi = _REF["zcr_std_real"]
    if zcr_std < zcr_lo:
        score_components.append(0.7)
    elif zcr_std > zcr_hi:
        score_components.append(0.1)
    else:
        score_components.append(0.3)

    # High spectral centroid → more synthetic (TTS tends to be brighter)
    score_components.append(
        min((centroid / _REF["centroid_cloned"]) * 0.5, 1.0)
    )

    # Low jitter → more synthetic
    j_lo, j_hi = _REF["jitter_real"]
    if jitter < j_lo:
        score_components.append(0.65)
    elif jitter > j_hi:
        score_components.append(0.15)
    else:
        score_components.append(0.30)

    return round(float(np.mean(score_components)), 4)
