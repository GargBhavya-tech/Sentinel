"""The Symbolic Contradiction Reconciler (build-map ticket #15).

The LLM-backed agents PROPOSE structured claims. This module DISPOSES: plain,
deterministic Python with no model in the decision path, so the verdict logic is
auditable line by line and cannot be talked out of its judgment.

Cross-examines across three axes: visual vs. structured total, tone vs. baseline,
voice vs. baseline, plus prompt-injection-as-evidence.
"""

from __future__ import annotations

from typing import Optional

from .claims import Claim, Contradiction, Verdict

RATIO_TRIGGER = 2.0
RATIO_WEIGHT = 0.6
TONE_TRIGGER = 0.60
TONE_WEIGHT = 0.30
VOICE_TRIGGER = 0.60
VOICE_WEIGHT = 0.35
DOMAIN_YOUNG_DAYS = 30
DOMAIN_WEIGHT = 0.20
INJECTION_WEIGHT = 0.25

FRAUD_AT = 0.60
REVIEW_AT = 0.30

# Solo-escalation: the engine must never be weaker than a naive single-model
# check. A single independently-extreme signal floors the risk.
SOLO_RATIO = 10.0
SOLO_TONE = 0.90
SOLO_VOICE = 0.90
SOLO_DOMAIN_DAYS = 3
SOLO_FLOOR = 0.90


def _get(claims, name, default=None):
    c = claims.get(name)
    return c.value if c is not None else default


def _ptr(claims, name):
    c = claims.get(name)
    return c.source_pointer if c is not None else None


def reconcile(claims: list[Claim]) -> Verdict:
    by_field = {c.field: c for c in claims}
    contradictions: list[Contradiction] = []

    visual = _get(by_field, "visual_total")
    structured = _get(by_field, "structured_total")
    if visual is not None and structured is not None:
        lo = max(min(visual, structured), 1e-9)
        ratio = max(visual, structured) / lo
        if ratio >= RATIO_TRIGGER:
            contradictions.append(
                Contradiction(
                    axis="visual_vs_structured",
                    detail=f"Shown total {visual:,.0f} contradicts charged total {structured:,.0f} ({ratio:.1f}x mismatch)",
                    weight=RATIO_WEIGHT,
                    evidence=[
                        p
                        for p in (
                            _ptr(by_field, "visual_total"),
                            _ptr(by_field, "structured_total"),
                        )
                        if p
                    ],
                )
            )

    tone_anomaly = _get(by_field, "tone_anomaly")
    if tone_anomaly is not None and tone_anomaly >= TONE_TRIGGER:
        contradictions.append(
            Contradiction(
                axis="tone_vs_baseline",
                detail=f"Message tone deviates from sender's writing baseline (anomaly {tone_anomaly:.2f})",
                weight=TONE_WEIGHT,
                evidence=[p for p in (_ptr(by_field, "tone_anomaly"),) if p],
            )
        )

    voice_mismatch = _get(by_field, "voice_mismatch")
    if voice_mismatch is not None and voice_mismatch >= VOICE_TRIGGER:
        contradictions.append(
            Contradiction(
                axis="voice_vs_baseline",
                detail=f"Voice note fails linguistic-acoustic match to sender (mismatch {voice_mismatch:.2f})",
                weight=VOICE_WEIGHT,
                evidence=[p for p in (_ptr(by_field, "voice_mismatch"),) if p],
            )
        )

    domain_age = _get(by_field, "domain_age_days")
    if domain_age is not None and domain_age <= DOMAIN_YOUNG_DAYS and contradictions:
        contradictions.append(
            Contradiction(
                axis="young_domain",
                detail=f"Sender domain is only {domain_age} days old",
                weight=DOMAIN_WEIGHT,
                evidence=[p for p in (_ptr(by_field, "domain_age_days"),) if p],
            )
        )

    if bool(_get(by_field, "injection_present", False)):
        contradictions.append(
            Contradiction(
                axis="injection",
                detail="Embedded instruction-injection attempt found in the document",
                weight=INJECTION_WEIGHT,
                evidence=[p for p in (_ptr(by_field, "injection_present"),) if p],
            )
        )

    risk = min(1.0, sum(c.weight for c in contradictions))

    solo = _solo_extreme(by_field)
    if solo is not None:
        risk = max(risk, SOLO_FLOOR)
        if not any(c.axis == solo.axis for c in contradictions):
            contradictions.append(solo)

    if risk >= FRAUD_AT:
        label = "FRAUD_LIKELY"
    elif risk >= REVIEW_AT:
        label = "REVIEW"
    else:
        label = "CLEAR"

    return Verdict(
        risk=round(risk, 3),
        verdict=label,
        contradictions=contradictions,
        counterfactual=_counterfactual(by_field, label),
    )


def _solo_extreme(by_field) -> Optional[Contradiction]:
    visual = _get(by_field, "visual_total")
    structured = _get(by_field, "structured_total")
    if visual is not None and structured is not None:
        ratio = max(visual, structured) / max(min(visual, structured), 1e-9)
        if ratio >= SOLO_RATIO:
            return Contradiction(
                "visual_vs_structured",
                f"Blatant {ratio:.0f}x total mismatch",
                SOLO_FLOOR,
                [
                    p
                    for p in (
                        _ptr(by_field, "visual_total"),
                        _ptr(by_field, "structured_total"),
                    )
                    if p
                ],
            )
    tone = _get(by_field, "tone_anomaly")
    if tone is not None and tone >= SOLO_TONE:
        return Contradiction(
            "tone_vs_baseline",
            f"Extreme stylometric anomaly ({tone:.2f})",
            SOLO_FLOOR,
            [p for p in (_ptr(by_field, "tone_anomaly"),) if p],
        )
    voice = _get(by_field, "voice_mismatch")
    if voice is not None and voice >= SOLO_VOICE:
        return Contradiction(
            "voice_vs_baseline",
            f"Extreme voice-spoof score ({voice:.2f})",
            SOLO_FLOOR,
            [p for p in (_ptr(by_field, "voice_mismatch"),) if p],
        )
    domain_age = _get(by_field, "domain_age_days")
    if domain_age is not None and domain_age <= SOLO_DOMAIN_DAYS:
        return Contradiction(
            "young_domain",
            f"Sender domain registered {domain_age} day(s) ago",
            SOLO_FLOOR,
            [p for p in (_ptr(by_field, "domain_age_days"),) if p],
        )
    if bool(_get(by_field, "injection_present", False)):
        return Contradiction(
            "injection",
            "Embedded instruction-injection attempt (malicious on its own)",
            SOLO_FLOOR,
            [p for p in (_ptr(by_field, "injection_present"),) if p],
        )
    return None


def _counterfactual(by_field, label) -> Optional[str]:
    if label == "CLEAR":
        return None
    parts = []
    visual = _get(by_field, "visual_total")
    structured = _get(by_field, "structured_total")
    if visual is not None and structured is not None and visual != structured:
        parts.append("the shown and charged totals matched")
    tone = _get(by_field, "tone_anomaly")
    if tone is not None and tone >= TONE_TRIGGER:
        parts.append("the message matched the sender's writing baseline")
    domain_age = _get(by_field, "domain_age_days")
    if domain_age is not None and domain_age <= DOMAIN_YOUNG_DAYS:
        parts.append("the sender domain were older than 30 days")
    if not parts:
        return None
    return "This would be CLEAR if " + " AND ".join(parts) + "."
