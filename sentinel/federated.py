"""Federated Pattern Network — build-map ticket #29.

⬜ FAKE / SEED — Build ONLY a simulated version: check a **hashed** fingerprint
against a **locally seeded** fake dataset of "other orgs." Label it simulated
on camera.

⛔ DO NOT BUILD real cross-org integration. Roadmap only.

Done when: "This template (hashed) was flagged at 2 other orgs" prints from
the seed data.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

# ── Seeded fake dataset of "other orgs" ───────────────────────────────────────
# Each entry is a hashed fingerprint (SHA-256 of the pattern) + metadata.
# These represent patterns supposedly seen at other orgs in the federated network.
# In production this would be a privacy-preserving bloom filter query over a
# consortium API. For the demo: a locally seeded dict.

_SEED_DATASET: list[dict] = [
    {
        "fingerprint_hash": hashlib.sha256(b"invoice_ratio_mismatch:offshore_belize:young_domain").hexdigest(),
        "pattern_type": "invoice_fraud",
        "orgs_flagged": 3,
        "first_seen_days_ago": 14,
        "confidence": 0.91,
        "description": "Invoice total mismatch + offshore routing to Belize + domain <30d",
    },
    {
        "fingerprint_hash": hashlib.sha256(b"ceo_voice_clone:vishing:wire_transfer").hexdigest(),
        "pattern_type": "vishing_bec",
        "orgs_flagged": 5,
        "first_seen_days_ago": 7,
        "confidence": 0.97,
        "description": "Cloned executive voice note requesting urgent wire transfer",
    },
    {
        "fingerprint_hash": hashlib.sha256(b"stylometric_anomaly:new_vendor:round_amount").hexdigest(),
        "pattern_type": "account_takeover",
        "orgs_flagged": 2,
        "first_seen_days_ago": 21,
        "confidence": 0.84,
        "description": "Stylometric deviation + new vendor + suspiciously round amount",
    },
    {
        "fingerprint_hash": hashlib.sha256(b"prompt_injection:hidden_text:invoice").hexdigest(),
        "pattern_type": "ai_evasion",
        "orgs_flagged": 1,
        "first_seen_days_ago": 3,
        "confidence": 0.99,
        "description": "Prompt injection attempt embedded in invoice white-on-white text",
    },
    {
        "fingerprint_hash": hashlib.sha256(b"vpn_geo_mismatch:concurrent_login:singapore").hexdigest(),
        "pattern_type": "geo_anomaly",
        "orgs_flagged": 4,
        "first_seen_days_ago": 10,
        "confidence": 0.88,
        "description": "VPN geolocation mismatch + concurrent login from different continent",
    },
]

# Build lookup index: hash → entry
_INDEX: dict[str, dict] = {e["fingerprint_hash"]: e for e in _SEED_DATASET}


# ── Fingerprint generation ─────────────────────────────────────────────────────

def compute_fingerprint(
    contradiction_axes: list[str],
    domain_age_flag: bool = False,
    has_voice: bool = False,
    has_injection: bool = False,
) -> str:
    """Compute a hashed pattern fingerprint from a case's signals.

    The hash is derived from the *types* of signals, not the raw values,
    so it can be checked against other orgs' patterns without exposing PII.
    """
    parts: list[str] = sorted(contradiction_axes)
    if domain_age_flag:
        parts.append("young_domain")
    if has_voice:
        parts.append("voice_mismatch")
    if has_injection:
        parts.append("prompt_injection")

    fingerprint_str = ":".join(parts)
    return hashlib.sha256(fingerprint_str.encode()).hexdigest()


# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class FederatedMatch:
    fingerprint_hash: str
    pattern_type: str
    orgs_flagged: int
    first_seen_days_ago: int
    confidence: float
    description: str
    simulated: bool = True


@dataclass
class FederatedResult:
    fingerprint_hash: str
    matches: list[FederatedMatch] = field(default_factory=list)
    simulated: bool = True          # ALWAYS True for hackathon
    disclaimer: str = (
        "⚠️ SIMULATED FEDERATED NETWORK — Pattern check against a locally "
        "seeded dataset of anonymised fingerprints. No real cross-org data."
    )

    def to_dict(self) -> dict:
        return {
            "fingerprint_hash": self.fingerprint_hash[:16] + "…",
            "simulated": self.simulated,
            "disclaimer": self.disclaimer,
            "matches_found": len(self.matches),
            "matches": [
                {
                    "pattern_type": m.pattern_type,
                    "orgs_flagged": m.orgs_flagged,
                    "first_seen_days_ago": m.first_seen_days_ago,
                    "confidence": m.confidence,
                    "description": m.description,
                }
                for m in self.matches
            ],
            "summary": self._summary(),
        }

    def _summary(self) -> str:
        if not self.matches:
            return "No matching pattern found in the federated seed dataset. [SIMULATED]"
        top = self.matches[0]
        return (
            f"This pattern (hashed) was flagged at {top.orgs_flagged} other org(s) "
            f"in the last {top.first_seen_days_ago} day(s). "
            f"Pattern type: {top.pattern_type}. [SIMULATED]"
        )


# ── Public API ─────────────────────────────────────────────────────────────────

def check_federation(
    case_id: str,
    contradiction_axes: list[str],
    domain_age_flag: bool = False,
    has_voice: bool = False,
    has_injection: bool = False,
) -> FederatedResult:
    """Check a case's fingerprint against the seeded federated pattern dataset.

    ⛔ BUILD-MAP: This is a SIMULATED check. No real network calls. No real
    cross-org data. Fingerprinits are SHA-256 hashes — no raw case data shared.

    Parameters
    ----------
    case_id : str
        For logging only.
    contradiction_axes : list[str]
        The axes that fired in the reconciler (e.g. ["visual_vs_structured"]).
    domain_age_flag : bool
        Whether a young-domain contradiction fired.
    has_voice : bool
        Whether a voice-mismatch was detected.
    has_injection : bool
        Whether a prompt injection was detected.

    Returns
    -------
    FederatedResult
        Matches from the seed dataset, with simulated=True always set.
    """
    fp = compute_fingerprint(
        contradiction_axes, domain_age_flag, has_voice, has_injection
    )
    log.info(
        "FederatedNetwork: SIMULATED check — case %s fingerprint %s…",
        case_id[:8], fp[:12],
    )

    # Exact match against seed index
    exact: list[FederatedMatch] = []
    if fp in _INDEX:
        entry = _INDEX[fp]
        exact.append(FederatedMatch(**{**entry, "simulated": True}))

    # If no exact match, find best approximate match by axis overlap
    # (for demo robustness — the demo case axes may not perfectly hash-match)
    if not exact:
        for entry in _SEED_DATASET:
            # Heuristic: if case has voice + BEC axes, match the vishing entry
            if has_voice and "vishing_bec" in entry["pattern_type"]:
                exact.append(FederatedMatch(**{**entry, "simulated": True}))
                break
            # If injection present, match the AI evasion entry
            if has_injection and "ai_evasion" in entry["pattern_type"]:
                exact.append(FederatedMatch(**{**entry, "simulated": True}))
                break
            # If offshore/mismatch axes, match invoice_fraud
            if any("visual" in ax or "structured" in ax for ax in contradiction_axes):
                exact.append(FederatedMatch(**{**entry, "simulated": True}))
                break

    result = FederatedResult(
        fingerprint_hash=fp,
        matches=exact,
        simulated=True,
    )

    log.info(
        "FederatedNetwork: %d match(es) found for case %s [SIMULATED]",
        len(exact), case_id[:8],
    )
    return result
