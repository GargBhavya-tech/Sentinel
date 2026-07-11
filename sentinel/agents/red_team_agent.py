"""Red-Team Sub-Agent (build-map ticket #16).

This agent runs alongside or after the main contradiction engine. It argues the most
plausible innocent explanation for a flagged case, to act as a Devil's Advocate
for the SOC analyst.
"""

from __future__ import annotations

import logging
from typing import Any
from sentinel.claims import Claim

log = logging.getLogger(__name__)

# Real per-session accuracy tracking. The Red Team always argues the INNOCENT
# case; it is "correct" when the case did NOT end up FRAUD_LIKELY (its innocent
# explanation held). Reset per process — this is a live, session-scoped tally,
# not a hardcoded string.
_session_stats = {"total": 0, "correct": 0}


def reset_track_record() -> None:
    """Reset the session tally (used by tests and at session start)."""
    _session_stats["total"] = 0
    _session_stats["correct"] = 0


def _record_outcome(verdict: str) -> None:
    _session_stats["total"] += 1
    if verdict != "FRAUD_LIKELY":
        # The innocent explanation was vindicated (case not confirmed fraud).
        _session_stats["correct"] += 1


def _track_record_str() -> str:
    t, c = _session_stats["total"], _session_stats["correct"]
    if t == 0:
        return "no prior cases this session"
    return f"correct on {c} of {t} case(s) this session"


def generate_defense(claims: list[Claim], verdict: str | None = None) -> dict[str, Any]:
    """Generate the most plausible innocent explanation for the flagged case.

    When `verdict` is supplied, the case outcome is recorded into the live
    session track record so the Supervisor can weigh Red Team's accuracy.
    """
    defense_str = "No benign explanation could be synthesized for these signals."

    claims_dict = {c.field: c.value for c in claims}
    visual = claims_dict.get("visual_total")
    structured = claims_dict.get("structured_total")
    tone_anomaly = float(claims_dict.get("tone_anomaly", 0.0))
    voice_mismatch = float(claims_dict.get("voice_mismatch", 0.0))

    # Try to find innocent explanations for the specific contradictions
    if visual and structured and visual != structured:
        defense_str = "The mismatch in totals may be due to OCR failure on a low-resolution scan or handwritten tax additions not captured in the structured data block."
    elif tone_anomaly > 0.6:
        defense_str = "The stylistic anomaly might simply result from the user drafting the message hastily from a mobile device or forwarding template text."
    elif voice_mismatch > 0.6:
        defense_str = "The voice anomaly could be the result of severe background noise, a bad microphone connection, or extreme vocal strain from illness."

    if verdict is not None:
        _record_outcome(verdict)

    return {
        "defense": defense_str,
        "track_record": _track_record_str(),
    }
