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

from typing import Any

from .agents.mock_agents import extract_claims
from .claims import Verdict
from .reconciler import reconcile

# Hard, single-signal thresholds for the OFF baseline. Each corresponds to one
# agent screaming on its own. If none scream individually, the baseline is CLEAR.
SOLO_RATIO = 10.0        # a 10x+ total mismatch is obvious even to a naive check
SOLO_TONE = 0.90         # an extreme stylometric anomaly
SOLO_VOICE = 0.90        # an extreme voice-spoof score
SOLO_DOMAIN_DAYS = 3     # a domain registered in the last couple of days


def run_case(case_id: str, metrics: dict[str, Any], contradiction_engine: str = "on") -> Verdict:
    claims = extract_claims(case_id, metrics)
    if contradiction_engine == "on":
        return reconcile(claims)
    if contradiction_engine == "off":
        return _single_model_baseline(metrics)
    raise ValueError("contradiction_engine must be 'on' or 'off'")


def _single_model_baseline(m: dict[str, Any]) -> Verdict:
    """Per-agent scoring with no cross-examination (the baseline everyone ships)."""
    visual = m.get("visual_total")
    structured = m.get("structured_total")
    ratio = 1.0
    if visual and structured:
        ratio = max(visual, structured) / max(min(visual, structured), 1e-9)

    solo_hit = (
        ratio >= SOLO_RATIO
        or m.get("tone_anomaly", 0.0) >= SOLO_TONE
        or m.get("voice_mismatch", 0.0) >= SOLO_VOICE
        or m.get("domain_age_days", 999) <= SOLO_DOMAIN_DAYS
        or bool(m.get("injection_present", False))
    )
    verdict = "FRAUD_LIKELY" if solo_hit else "CLEAR"
    risk = 0.9 if solo_hit else 0.05
    return Verdict(risk=risk, verdict=verdict, contradictions=[], counterfactual=None)
