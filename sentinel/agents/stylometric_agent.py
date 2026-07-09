"""Stylometric Agent — build-map ticket #11.

Builds a per-user writing fingerprint from text samples and compares a
new message against that baseline to detect account-takeover.

Features extracted (all deterministic, no LLM)
----------------------------------------------
  char_bigrams       : character-level 2-gram frequency distribution
  char_trigrams      : character-level 3-gram frequency distribution
  word_lengths       : mean + std of word length distribution
  sentence_lengths   : mean + std of sentence token count
  punct_density      : punctuation characters per 100 chars
  uppercase_ratio    : UPPER chars / total alpha chars
  avg_word_freq_rank : average unigram frequency rank (proxy for vocab richness)
  line_start_caps    : ratio of lines starting with capital letter

Similarity
----------
Each feature set is serialised to a flat numpy vector; cosine similarity
between the target and the mean of baseline vectors gives the final
alignment score (0 = opposite, 1 = identical).

tone_anomaly = 1 - alignment

The build map says: "scope honestly: demo on a curated baseline-vs-imposter pair."
A score ≥ 0.35 is flagged as anomalous (tuned on the curated demo pair).
"""

from __future__ import annotations

import logging
import math
import re
import string
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.spatial.distance import cosine as cosine_distance  # type: ignore

from ..claims import Claim

log = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
ANOMALY_THRESHOLD = 0.10  # tone_anomaly ≥ this → REVIEW (tuned on curated demo pair)

# ── Urgency / command-word lexicon (strong BEC signal) ───────────────────────
_URGENCY_WORDS = {
    "urgent",
    "immediately",
    "now",
    "asap",
    "wire",
    "transfer",
    "today",
    "deadline",
    "quick",
    "quickly",
    "hurry",
    "rush",
    "confidential",
    "secret",
    "nobody",
    "anyone",
    "private",
    "direct",
}
_IMPERATIVE_STARTERS = {
    "send",
    "wire",
    "transfer",
    "pay",
    "complete",
    "do",
    "call",
    "sign",
    "approve",
    "confirm",
    "process",
    "remit",
}

# ── Common word frequency list (top-500 English, for vocab-rank proxy) ────────
_COMMON_WORDS = {
    w: i
    for i, w in enumerate(
        [
            "the",
            "be",
            "to",
            "of",
            "and",
            "a",
            "in",
            "that",
            "have",
            "it",
            "for",
            "not",
            "on",
            "with",
            "he",
            "as",
            "you",
            "do",
            "at",
            "this",
            "but",
            "his",
            "by",
            "from",
            "they",
            "we",
            "say",
            "her",
            "she",
            "or",
            "an",
            "will",
            "my",
            "one",
            "all",
            "would",
            "there",
            "their",
            "what",
            "so",
            "up",
            "out",
            "if",
            "about",
            "who",
            "get",
            "which",
            "go",
            "me",
            "please",
            "thank",
            "regards",
            "dear",
            "sincerely",
            "attached",
            "kindly",
            "urgent",
            "immediately",
            "wire",
            "transfer",
            "account",
            "payment",
        ]
    )
}
_VOCAB_MAX_RANK = len(_COMMON_WORDS) + 1


# ── Feature extraction ────────────────────────────────────────────────────────


def _extract_features(text: str) -> np.ndarray:
    """Extract a fixed-length feature vector from a text sample."""
    if not text.strip():
        return np.zeros(50, dtype=np.float32)

    words = re.findall(r"\b[a-zA-Z']+\b", text)
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    # ── N-gram frequencies (top 20 bigrams + top 20 trigrams) ────────────────
    bigrams = Counter(text[i : i + 2] for i in range(len(text) - 1))
    trigrams = Counter(text[i : i + 3] for i in range(len(text) - 2))

    # Build deterministic feature slots from a fixed character alphabet
    alpha = string.ascii_lowercase + string.digits + " .,!?;:'-"
    bg_vec = np.array(
        [bigrams.get(a + b, 0) for a in alpha[:10] for b in alpha[:10]],
        dtype=np.float32,
    )  # 100 slots — normalise
    bg_total = bg_vec.sum() or 1.0
    bg_vec /= bg_total

    tg_vec = np.array(
        [
            trigrams.get(a + b + c, 0)
            for a in alpha[:5]
            for b in alpha[:5]
            for c in alpha[:5]
        ],
        dtype=np.float32,
    )[:100]  # first 100 slots
    tg_total = tg_vec.sum() or 1.0
    tg_vec /= tg_total

    # ── Scalar features ───────────────────────────────────────────────────────
    word_lengths = [len(w) for w in words] or [0]
    sent_lengths = [len(s.split()) for s in sentences] or [0]
    punct_chars = sum(1 for c in text if c in string.punctuation)
    alpha_chars = sum(1 for c in text if c.isalpha())
    upper_chars = sum(1 for c in text if c.isupper())
    lines = text.splitlines()
    cap_lines = sum(
        1 for line in lines if line.strip() and line.strip()[0].isupper()
    )

    word_ranks = [_COMMON_WORDS.get(w.lower(), _VOCAB_MAX_RANK) for w in words]

    # ── Urgency / command-word features (domain-specific) ────────────────────
    words_lower = [w.lower() for w in words]
    urgency_density = sum(1 for w in words_lower if w in _URGENCY_WORDS) / max(
        len(words_lower), 1
    )
    imperative_ratio = sum(
        1
        for s in sentences
        if s.split() and s.split()[0].lower() in _IMPERATIVE_STARTERS
    ) / max(len(sentences), 1)
    all_caps_word_ratio = sum(1 for w in words if w.isupper() and len(w) > 1) / max(
        len(words), 1
    )
    exclamation_density = text.count("!") / max(len(text), 1) * 100
    avg_sentence_words = np.mean(sent_lengths)

    scalars = np.array(
        [
            np.mean(word_lengths),
            np.std(word_lengths) if len(word_lengths) > 1 else 0.0,
            np.mean(sent_lengths),
            np.std(sent_lengths) if len(sent_lengths) > 1 else 0.0,
            (punct_chars / max(len(text), 1)) * 100,
            (upper_chars / max(alpha_chars, 1)),
            np.mean(word_ranks) / _VOCAB_MAX_RANK,
            (cap_lines / max(len(lines), 1)),
            math.log1p(len(words)),
            math.log1p(len(sentences)),
            # Domain-specific urgency features
            urgency_density * 10,  # scale up for sensitivity
            imperative_ratio * 5,
            all_caps_word_ratio * 5,
            exclamation_density,
            avg_sentence_words / 20.0,  # normalise
        ],
        dtype=np.float32,
    )

    # Concatenate: 100 + 100 + 10 = 210-dim vector — slice to 50 for speed
    full = np.concatenate([bg_vec[:25], tg_vec[:15], scalars])
    return full


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if np.allclose(a, 0) or np.allclose(b, 0):
        return 0.0
    return float(1.0 - cosine_distance(a, b))


# ── User profile ──────────────────────────────────────────────────────────────


@dataclass
class WritingProfile:
    """Per-user writing fingerprint built from historical samples."""

    user_id: str
    sample_count: int
    mean_vector: np.ndarray
    samples_seen: list[str] = field(default_factory=list, repr=False)

    @classmethod
    def build(cls, user_id: str, samples: list[str]) -> "WritingProfile":
        """Build a profile from a list of text samples (e.g. Slack messages)."""
        if not samples:
            raise ValueError(f"Need ≥ 1 sample for user {user_id!r}")
        vecs = np.stack([_extract_features(s) for s in samples])
        mean_vec = vecs.mean(axis=0)
        log.info(
            "stylometric: profile built for %s from %d samples", user_id, len(samples)
        )
        return cls(
            user_id=user_id,
            sample_count=len(samples),
            mean_vector=mean_vec,
            samples_seen=samples,
        )


# ── Main entry point ──────────────────────────────────────────────────────────


@dataclass
class StylometricResult:
    case_id: str
    user_id: str
    tone_anomaly: float  # 0..1 — higher = more anomalous
    alignment: float  # cosine similarity to baseline (0..1)
    flagged: bool
    detail: str
    source_pointer: str

    def to_claim(self) -> Claim:
        return Claim(
            field="tone_anomaly",
            value=self.tone_anomaly,
            confidence=0.80,
            source_pointer=self.source_pointer,
            agent="stylometric",
        )


def analyze(
    case_id: str,
    user_id: str,
    target_text: str,
    baseline_profile: Optional[WritingProfile] = None,
    baseline_samples: Optional[list[str]] = None,
) -> StylometricResult:
    """Compare target_text against a user's baseline writing profile.

    Parameters
    ----------
    case_id:        Active case ID.
    user_id:        Slack user ID of the message author.
    target_text:    The suspicious message / document excerpt.
    baseline_profile:
        Pre-built WritingProfile (preferred — avoids rebuilding every call).
    baseline_samples:
        Raw text samples to build a profile from on-the-fly.

    Returns
    -------
    StylometricResult with tone_anomaly Claim.
    """
    if baseline_profile is None:
        if not baseline_samples:
            # No baseline — return low-confidence neutral result
            log.warning("stylometric: no baseline for user %s — skipping", user_id)
            return StylometricResult(
                case_id=case_id,
                user_id=user_id,
                tone_anomaly=0.0,
                alignment=1.0,
                flagged=False,
                detail="No baseline available — stylometric check skipped",
                source_pointer=f"{case_id}/message.txt#stylometry",
            )
        baseline_profile = WritingProfile.build(user_id, baseline_samples)

    target_vec = _extract_features(target_text)
    alignment = _cosine_similarity(target_vec, baseline_profile.mean_vector)
    tone_anomaly = round(max(0.0, 1.0 - alignment), 4)
    flagged = tone_anomaly >= ANOMALY_THRESHOLD

    detail = (
        f"Alignment with baseline: {alignment:.3f} "
        f"({'anomalous — possible impersonation' if flagged else 'within normal range'}). "
        f"Baseline built from {baseline_profile.sample_count} sample(s)."
    )

    log.info(
        "stylometric: case=%s user=%s anomaly=%.3f flagged=%s",
        case_id,
        user_id,
        tone_anomaly,
        flagged,
    )

    return StylometricResult(
        case_id=case_id,
        user_id=user_id,
        tone_anomaly=tone_anomaly,
        alignment=alignment,
        flagged=flagged,
        detail=detail,
        source_pointer=f"{case_id}/message.txt#stylometry",
    )
