"""The investigation pipeline, with the ablation switch that powers ticket #34.

`run_case(..., contradiction_engine="on")` uses the full cross-examination
(the Sentinel differentiator).

`run_case(..., contradiction_engine="off")` is the honest baseline every
competitor ships: single-model / per-agent scoring that flags a case only when
some *individual* signal is independently extreme. It has no way to combine
moderate signals across modalities — which is exactly what the flagship
"contradiction-only" case exploits.

The gap between the two is the number we put on screen in the demo.
"""

from __future__ import annotations


from .claims import Verdict, Claim
from .reconciler import reconcile

# Hard, single-signal thresholds for the OFF baseline. Each corresponds to one
# agent screaming on its own. If none scream individually, the baseline is CLEAR.
SOLO_RATIO = 10.0  # a 10x+ total mismatch is obvious even to a naive check
SOLO_TONE = 0.90  # an extreme stylometric anomaly
SOLO_VOICE = 0.90  # an extreme voice-spoof score
SOLO_DOMAIN_DAYS = 3  # a domain registered in the last couple of days


def run_case(claims: list[Claim], contradiction_engine: str = "on") -> Verdict:
    if contradiction_engine == "on":
        return reconcile(claims)
    if contradiction_engine == "off":
        return _single_model_baseline(claims)
    raise ValueError("contradiction_engine must be 'on' or 'off'")


def _single_model_baseline(claims: list[Claim]) -> Verdict:
    """Per-agent scoring with no cross-examination (the baseline everyone ships)."""
    claims_dict = {c.field: c.value for c in claims}

    visual = claims_dict.get("visual_total")
    structured = claims_dict.get("structured_total")
    tone_anomaly = claims_dict.get("tone_anomaly", 0.0)
    voice_mismatch = claims_dict.get("voice_mismatch", 0.0)
    domain_age_days = claims_dict.get("domain_age_days", 999)
    injection_present = bool(claims_dict.get("injection_present", False))

    ratio = 1.0
    if visual and structured:
        ratio = max(visual, structured) / max(min(visual, structured), 1e-9)

    solo_hit = (
        ratio >= SOLO_RATIO
        or tone_anomaly >= SOLO_TONE
        or voice_mismatch >= SOLO_VOICE
        or domain_age_days <= SOLO_DOMAIN_DAYS
        or injection_present
    )
    verdict = "FRAUD_LIKELY" if solo_hit else "CLEAR"
    risk = 0.9 if solo_hit else 0.05
    return Verdict(risk=risk, verdict=verdict, contradictions=[], counterfactual=None)
