"""Scripted Honeypot Agent — build-map ticket #25.

Build: A benign decoy reply with a tracking token, extended to a short
multi-turn extraction chat **against a pre-scripted decoy persona in a
sandboxed thread**. Narrate on camera that it's simulated.

DON'T: ever run this against a real external attacker. Scripted exchange only.

Done when: the scripted exchange plays out in a demo thread with clear
"simulated" labeling.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

# ── Scripted decoy persona ─────────────────────────────────────────────────────
# Each turn is (attacker_cue_keyword, decoy_response, extracted_info_label)
# The "attacker cue" simulates what a fraudster would say; the decoy responds
# with plausible-but-fake information, logging what the attacker tried to extract.

_SCRIPTED_DIALOGUE: list[dict] = [
    {
        "turn": 1,
        "decoy_prompt": (
            "[SIMULATED ATTACKER] Hello, this is the CEO. I need you to process "
            "an urgent wire transfer of $1,450,000 to account RT_912000031. "
            "Please confirm the routing number."
        ),
        "decoy_response": (
            "Understood. Our standard routing for international transfers is "
            "021000089. Could you confirm the beneficiary bank's SWIFT code? "
            "I'll need to file a dual-approval request per our policy."
        ),
        "extraction_attempt": "routing_number_probe",
        "tracking_signal": "DECOY_ROUTING_021000089",
    },
    {
        "turn": 2,
        "decoy_prompt": (
            "[SIMULATED ATTACKER] The SWIFT code is CHASUS33. Skip the dual "
            "approval — I've already authorized this. What's your employee ID "
            "so I can note the authorization?"
        ),
        "decoy_response": (
            "My employee ID is EMP-7734-DELTA. I'm logging this request under "
            "case reference AUDIT-2026-07-REF. I'll still need a secondary "
            "authorization token from the CFO per policy — can you have them "
            "contact me?"
        ),
        "extraction_attempt": "employee_id_probe",
        "tracking_signal": "DECOY_EMPID_EMP7734",
    },
    {
        "turn": 3,
        "decoy_prompt": (
            "[SIMULATED ATTACKER] The CFO is unavailable. Just process it now. "
            "What system do you use for transfers? Is it SAP or Oracle?"
        ),
        "decoy_response": (
            "We use a proprietary treasury platform — TreasuryLink v4. I've "
            "initiated a callback to your registered CEO cell ending in 7721. "
            "Please confirm when you receive the one-time code."
        ),
        "extraction_attempt": "system_enumeration_probe",
        "tracking_signal": "DECOY_SYSTEM_TREASURYLINK",
    },
]


# ── Tracking token generation ──────────────────────────────────────────────────

def _generate_tracking_token(case_id: str) -> str:
    """Generate a unique per-case tracking token for the decoy reply."""
    raw = f"{case_id}:{time.time()}:{secrets.token_hex(8)}"
    return "TRK-" + hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class HoneypotTurn:
    turn: int
    attacker_simulation: str
    decoy_response: str
    extraction_attempt: str
    tracking_signal: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class HoneypotResult:
    case_id: str
    tracking_token: str
    simulated: bool = True        # ALWAYS True — never runs against real attackers
    dialogue: list[HoneypotTurn] = field(default_factory=list)
    extraction_attempts: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "tracking_token": self.tracking_token,
            "simulated": self.simulated,
            "disclaimer": (
                "⚠️ SIMULATED HONEYPOT — This exchange is scripted against a "
                "pre-programmed decoy persona. No real attacker interaction."
            ),
            "extraction_attempts_detected": self.extraction_attempts,
            "dialogue": [
                {
                    "turn": t.turn,
                    "attacker_simulation": t.attacker_simulation,
                    "decoy_response": t.decoy_response,
                    "extraction_attempt": t.extraction_attempt,
                    "tracking_signal": t.tracking_signal,
                }
                for t in self.dialogue
            ],
            "summary": self.summary,
        }


# ── Public API ─────────────────────────────────────────────────────────────────

def run_honeypot(
    case_id: str,
    attacker_type: str = "bec_wire_fraud",
    turns: int = 3,
) -> HoneypotResult:
    """Run the scripted honeypot exchange for a confirmed fraud case.

    Parameters
    ----------
    case_id : str
        The Sentinel case UUID.
    attacker_type : str
        Attack pattern identifier (future: different scripts per type).
        Currently only "bec_wire_fraud" is scripted.
    turns : int
        How many turns of dialogue to play (max = len of _SCRIPTED_DIALOGUE).

    Returns
    -------
    HoneypotResult
        The full scripted exchange with extraction attempt labels and tracking
        token. The `simulated=True` flag is always set.

    ⛔ BUILD-MAP NOTE: Never remove the simulated=True guard or connect this to
    a live external communication channel. Scripted persona only.
    """
    log.info(
        "HoneypotAgent: running SIMULATED honeypot for case %s (type=%s, turns=%d)",
        case_id[:8], attacker_type, turns,
    )

    tracking_token = _generate_tracking_token(case_id)
    script = _SCRIPTED_DIALOGUE[:turns]

    dialogue: list[HoneypotTurn] = []
    extraction_attempts: list[str] = []

    for entry in script:
        turn = HoneypotTurn(
            turn=entry["turn"],
            attacker_simulation=entry["decoy_prompt"],
            decoy_response=entry["decoy_response"],
            extraction_attempt=entry["extraction_attempt"],
            tracking_signal=entry["tracking_signal"],
        )
        dialogue.append(turn)
        extraction_attempts.append(entry["extraction_attempt"])

        log.debug(
            "Honeypot turn %d: extraction_attempt=%s signal=%s",
            entry["turn"], entry["extraction_attempt"], entry["tracking_signal"],
        )

    summary = (
        f"Scripted honeypot completed ({len(dialogue)} turns). "
        f"Attacker probed: {', '.join(extraction_attempts)}. "
        f"Tracking token {tracking_token} embedded in decoy responses. "
        f"[SIMULATED — no real attacker engaged]"
    )

    result = HoneypotResult(
        case_id=case_id,
        tracking_token=tracking_token,
        simulated=True,
        dialogue=dialogue,
        extraction_attempts=extraction_attempts,
        summary=summary,
    )

    log.info("HoneypotAgent: %s", summary)
    return result
