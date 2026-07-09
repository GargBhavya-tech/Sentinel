"""Deterministic 'agents' that emit structured claims from a case's metrics.

In the real system these are LLM-backed specialists (Vision/OCR, Finance,
Stylometric, Voice). Here they are deterministic stand-ins so the reconciler and
the eval harness can be built and tested *today*, with no API keys. When the real
agents land, they only need to produce the same `Claim` objects — the reconciler
and everything downstream is unchanged.

A "case metrics" dict is the pre-extracted evidence (what OCR/CSV parsing/voice
analysis would have produced). See sentinel/eval/dataset.py.
"""

from __future__ import annotations

from typing import Any

from ..claims import Claim


def extract_claims(case_id: str, m: dict[str, Any]) -> list[Claim]:
    """Turn a case's metrics into the structured claims each agent would emit."""
    claims: list[Claim] = []

    if "visual_total" in m:
        claims.append(Claim(
            field="visual_total", value=float(m["visual_total"]), confidence=0.95,
            source_pointer=f"{case_id}/invoice.png#bbox=[410,980,120,40]", agent="vision",
        ))
    if "structured_total" in m:
        claims.append(Claim(
            field="structured_total", value=float(m["structured_total"]), confidence=0.99,
            source_pointer=f"{case_id}/data.csv#R14C3", agent="finance",
        ))
    if "tone_anomaly" in m:
        claims.append(Claim(
            field="tone_anomaly", value=float(m["tone_anomaly"]), confidence=0.80,
            source_pointer=f"{case_id}/message.txt#stylometry", agent="stylometric",
        ))
    if "voice_mismatch" in m:
        claims.append(Claim(
            field="voice_mismatch", value=float(m["voice_mismatch"]), confidence=0.75,
            source_pointer=f"{case_id}/voicenote.wav#antispoof", agent="voice",
        ))
    if "domain_age_days" in m:
        claims.append(Claim(
            field="domain_age_days", value=int(m["domain_age_days"]), confidence=0.99,
            source_pointer=f"{case_id}/whois", agent="threat_intel",
        ))
    if m.get("injection_present"):
        claims.append(Claim(
            field="injection_present", value=True, confidence=0.99,
            source_pointer=f"{case_id}/invoice.png#hidden_text", agent="injection_scanner",
        ))
    return claims
