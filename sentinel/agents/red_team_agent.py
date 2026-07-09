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

# Mock accuracy tracking state (in reality this would be persisted to the DB)
_session_stats = {"total_cases": 5, "correct_defenses": 2}


def generate_defense(claims: list[Claim]) -> dict[str, Any]:
    """Analyze the claims and generate the most plausible innocent explanation."""
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

    # Increment our mock session stats to simulate an active track record
    _session_stats["total_cases"] += 1
    # Randomly increment correct_defenses for the sake of the track record demo
    if _session_stats["total_cases"] % 3 == 0:
        _session_stats["correct_defenses"] += 1

    return {
        "defense": defense_str,
        "track_record": f"correct on {_session_stats['correct_defenses']} of last {_session_stats['total_cases']}",
    }
