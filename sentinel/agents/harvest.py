"""Claim harvesting — the single seam between agents and the reconciler.

Agents historically expose EITHER `to_claims()` (plural, returns a list) OR
`to_claim()` (singular, returns one Claim). Both worker paths previously only
harvested `to_claims()`, so Stylometric (tone_anomaly), Voice (voice_mismatch),
and Policy (policy_violation) claims were silently dropped before they ever
reached the contradiction engine.

`harvest_claims` normalises any agent result into a list of Claims so no agent
output can be dropped again — regardless of which method shape it exposes.
"""

from __future__ import annotations

from sentinel.claims import Claim


def harvest_claims(result) -> list[Claim]:
    """Normalise any agent result into a list of Claims.

    Handles both the plural (`to_claims`) and singular (`to_claim`) contracts,
    plus exceptions and results with neither method (e.g. the compliance
    result, which is consumed separately).
    """
    if result is None or isinstance(result, Exception):
        return []
    if hasattr(result, "to_claims"):
        claims = result.to_claims()
        return list(claims) if claims else []
    if hasattr(result, "to_claim"):
        claim = result.to_claim()
        return [claim] if claim is not None else []
    return []
