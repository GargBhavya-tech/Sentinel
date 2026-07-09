"""NLP Agent — build-map ticket #9.

Scam-type classification, urgency detection, and keyword extraction on
the text body of a Slack message or attached document.

No LLM — pure pattern matching + a lightweight Naive-Bayes-style scorer
using a hand-crafted keyword lexicon. The build map says "multilingual /
code-switch aware if cheap" — we handle the most common mixed-language
BEC phrasings used in Indian and South-East Asian scam campaigns.

Output Claims
-------------
  scam_type  : str   — "BEC" | "INVOICE" | "ROMANCE" | "ADVANCE_FEE" |
                       "PHISHING" | "VISHING" | "UNKNOWN"
  urgency    : float — 0..1 urgency pressure score
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..claims import Claim

log = logging.getLogger(__name__)

# ── Scam lexicons ─────────────────────────────────────────────────────────────

_LEXICON: dict[str, list[str]] = {
    "BEC": [
        "wire transfer",
        "wire funds",
        "change bank",
        "new account",
        "banking details",
        "payment details updated",
        "urgently transfer",
        "cfo",
        "ceo request",
        "executive request",
        "strictly confidential",
        "do not discuss",
        "keep this private",
        "on behalf of the ceo",
        "direct transfer",
        "remit payment",
        "bypass approval",
        # Hinglish / code-switched variants
        "jaldi karo",
        "turant transfer",
        "abhi bhejo",
    ],
    "INVOICE": [
        "invoice attached",
        "payment overdue",
        "final notice",
        "account past due",
        "late fee",
        "collection agency",
        "legal action",
        "settlement required",
        "pay now",
        "immediate payment",
        "outstanding balance",
        "unpaid invoice",
        "past due balance",
        "your payment has not been received",
    ],
    "ROMANCE": [
        "i love you",
        "my darling",
        "send me money",
        "western union",
        "stuck in customs",
        "investment opportunity",
        "cryptocurrency",
        "i need your help",
        "fell in love",
        "soulmate",
        "military officer",
        "doctor abroad",
        "stranded",
    ],
    "ADVANCE_FEE": [
        "inheritance",
        "lottery",
        "selected beneficiary",
        "unclaimed funds",
        "million dollars",
        "transfer fee",
        "administrative fee",
        "secret funds",
        "diplomat",
        "box of money",
        "release fee",
        "nigerian prince",  # yes, still used
    ],
    "PHISHING": [
        "verify your account",
        "click the link",
        "your account will be suspended",
        "confirm your details",
        "update your password",
        "unusual activity",
        "login attempt",
        "reset your password",
        "account compromised",
        "verify identity",
        "suspended account",
    ],
    "VISHING": [
        "press 1 to speak",
        "call this number immediately",
        "irs agent",
        "tax authority",
        "arrest warrant",
        "social security",
        "your ssn has been suspended",
        "police department",
        "fraud department",
        "last warning call",
    ],
}

_URGENCY_PHRASES: list[tuple[str, float]] = [
    ("immediately", 0.20),
    ("urgent", 0.20),
    ("asap", 0.15),
    ("as soon as possible", 0.15),
    ("right now", 0.20),
    ("today only", 0.25),
    ("deadline", 0.10),
    ("last chance", 0.25),
    ("do not delay", 0.20),
    ("time-sensitive", 0.20),
    ("within the hour", 0.30),
    ("within 24 hours", 0.15),
    ("before end of day", 0.15),
    ("eod", 0.10),
    ("final notice", 0.25),
    ("do not tell anyone", 0.35),
    ("keep this secret", 0.35),
    ("confidential", 0.10),
    # Code-switched
    ("jaldi", 0.20),
    ("turant", 0.20),
]


# ── Result ─────────────────────────────────────────────────────────────────────


@dataclass
class NLPResult:
    case_id: str
    scam_type: str
    scam_confidence: float  # 0..1 probability-like score
    urgency: float  # 0..1 urgency pressure
    matched_keywords: list[str] = field(default_factory=list)
    urgency_phrases: list[str] = field(default_factory=list)

    def to_claims(self) -> list[Claim]:
        return [
            Claim(
                field="scam_type_score",
                value=self.scam_confidence,
                confidence=0.75,
                source_pointer=f"{self.case_id}/message.txt#nlp_scam",
                agent="nlp",
            ),
            Claim(
                field="urgency_score",
                value=self.urgency,
                confidence=0.80,
                source_pointer=f"{self.case_id}/message.txt#nlp_urgency",
                agent="nlp",
            ),
        ]


# ── Main entry point ───────────────────────────────────────────────────────────


def analyze(
    case_id: str,
    text: str,
    pre_metrics: Optional[dict] = None,
) -> NLPResult:
    """Classify the scam type and urgency of a text.

    Parameters
    ----------
    case_id: Active case ID.
    text:    Message body or document text.
    pre_metrics: Pre-extracted values (mock/test shortcut).
    """
    if pre_metrics and "tone_anomaly" in pre_metrics:
        # NLP not part of pre_metrics usually — just pass through
        pass

    lower = text.lower()

    # ── Score each scam type ──────────────────────────────────────────────────
    scores: dict[str, float] = {}
    all_keywords: list[str] = []

    for scam_type, keywords in _LEXICON.items():
        hits = [kw for kw in keywords if kw in lower]
        score = min(len(hits) / max(len(keywords) * 0.15, 1), 1.0)
        scores[scam_type] = score
        all_keywords.extend(hits)

    best_type = max(scores, key=lambda k: scores[k])
    best_score = scores[best_type]

    if best_score < 0.05:
        best_type = "UNKNOWN"

    # ── Urgency score ─────────────────────────────────────────────────────────
    urgency = 0.0
    urgency_hits: list[str] = []
    for phrase, weight in _URGENCY_PHRASES:
        if phrase in lower:
            urgency = min(urgency + weight, 1.0)
            urgency_hits.append(phrase)

    log.info(
        "nlp: case=%s scam_type=%s conf=%.3f urgency=%.3f",
        case_id,
        best_type,
        best_score,
        urgency,
    )

    return NLPResult(
        case_id=case_id,
        scam_type=best_type,
        scam_confidence=round(best_score, 4),
        urgency=round(urgency, 4),
        matched_keywords=list(set(all_keywords)),
        urgency_phrases=urgency_hits,
    )
