"""Rule synthesizer (build-map ticket #26).

Extracts a structured JSON detection rule from the signals of a confirmed
fraud verdict. The rule captures ONLY the signals that actually fired
(contradictions + claim values), so it's specific enough to be useful
without being so tight it never matches again.

No LLM in the synthesis path. The rule is derived deterministically from
the Verdict object.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..claims import Verdict, Claim
from .schema import Rule

log = logging.getLogger(__name__)

# How much headroom to give thresholds so the rule fires on the NEXT similar
# case (not just the exact one that generated it). We set thresholds slightly
# BELOW the observed value so near-matches also trigger.
_RATIO_SLACK = 0.85         # rule fires if ratio >= 85% of the observed ratio
_TONE_SLACK = 0.90          # rule fires if tone >= 90% of the observed score
_VOICE_SLACK = 0.90
_DOMAIN_SLACK_DAYS = 3      # rule fires if domain age < observed + 3 days


def synthesize_rule(
    case_id: str,
    verdict: Verdict,
    claims: list[Claim],
) -> Optional[Rule]:
    """Synthesize a detection rule from a FRAUD_LIKELY verdict.

    Returns None if the verdict is not FRAUD_LIKELY (we only auto-write
    rules on confirmed fraud — auto-enforcing from a REVIEW risks FP cascade).
    Returns None if no meaningful conditions can be extracted.
    """
    if verdict.verdict != "FRAUD_LIKELY":
        log.debug(
            "synthesize_rule: verdict=%r — not writing rule", verdict.verdict
        )
        return None

    claims_dict = {c.field: c.value for c in claims}

    # Extract which conditions fired
    ratio_threshold: Optional[float] = None
    tone_threshold: Optional[float] = None
    voice_threshold: Optional[float] = None
    domain_max: Optional[int] = None
    injection: Optional[bool] = None
    policy: Optional[bool] = None

    axes = {c.axis for c in verdict.contradictions}

    # ── visual vs structured ratio ─────────────────────────────────────────
    if "visual_vs_structured" in axes:
        visual = claims_dict.get("visual_total")
        structured = claims_dict.get("structured_total")
        if visual is not None and structured is not None:
            v, s = float(visual), float(structured)
            observed_ratio = max(v, s) / max(min(v, s), 1e-9)
            ratio_threshold = round(observed_ratio * _RATIO_SLACK, 2)

    # ── tone anomaly ───────────────────────────────────────────────────────
    if "tone_vs_baseline" in axes:
        tone = claims_dict.get("tone_anomaly")
        if tone is not None:
            tone_threshold = round(float(tone) * _TONE_SLACK, 3)

    # ── voice mismatch ─────────────────────────────────────────────────────
    # The reconciler emits this axis as "voice_vs_baseline" (see reconciler.py).
    if "voice_vs_baseline" in axes:
        voice = claims_dict.get("voice_mismatch")
        if voice is not None:
            voice_threshold = round(float(voice) * _VOICE_SLACK, 3)

    # ── domain age ─────────────────────────────────────────────────────────
    domain_age = claims_dict.get("domain_age_days")
    if domain_age is not None and int(domain_age) < 90:
        domain_max = int(domain_age) + _DOMAIN_SLACK_DAYS

    # ── injection ─────────────────────────────────────────────────────────
    if claims_dict.get("injection_present"):
        injection = True

    # ── policy violation ──────────────────────────────────────────────────
    if claims_dict.get("policy_violation"):
        policy = True

    # At least one condition must be set — otherwise it's a useless rule
    has_condition = any(
        x is not None
        for x in [
            ratio_threshold, tone_threshold, voice_threshold,
            domain_max, injection, policy,
        ]
    )
    if not has_condition:
        log.warning(
            "synthesize_rule: case=%s — no extractable conditions, skipping",
            case_id,
        )
        return None

    # Build human-readable description from fired axes
    parts = []
    if ratio_threshold is not None:
        parts.append(f"invoice ratio ≥ {ratio_threshold}×")
    if tone_threshold is not None:
        parts.append(f"tone anomaly ≥ {tone_threshold}")
    if voice_threshold is not None:
        parts.append(f"voice mismatch ≥ {voice_threshold}")
    if domain_max is not None:
        parts.append(f"domain age < {domain_max} days")
    if injection:
        parts.append("prompt injection detected")
    if policy:
        parts.append("policy violation")
    description = "Auto-synthesized from case " + case_id[:8] + ": " + " + ".join(parts)

    rule = Rule(
        source_case_id=case_id,
        status="shadow",  # always starts as shadow — analyst promotes to enforced
        ratio_threshold=ratio_threshold,
        tone_anomaly_threshold=tone_threshold,
        voice_mismatch_threshold=voice_threshold,
        domain_age_days_max=domain_max,
        injection_present=injection,
        policy_violation=policy,
        verdict="FRAUD_LIKELY",
        description=description,
    )
    log.info(
        "synthesize_rule: synthesized rule %s for case %s (axes=%r)",
        rule.rule_id[:8], case_id, sorted(axes),
    )
    return rule
