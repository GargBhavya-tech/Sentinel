"""Curated demo fixtures for the flagship investigation.

The live pipeline can only produce a voice/stylometric signal when a real audio
file and a writing baseline are supplied. For the 3-minute demo we instead
inject a *curated* set of claims that represent the canonical scenario — a
cloned-CEO voice note + impostor tone + forged invoice total + young offshore
domain — so all three contradiction axes fire legitimately on camera.

This is honestly labelled as curated (see Master Reference §13, "demo on a
curated real-clip-vs-cloned-clip pair"). Every claim carries a source_pointer
and confidence just like a real agent's output, and flows through the exact
same deterministic reconciler — nothing about the decision path is faked, only
the pre-extracted evidence values are fixed.
"""

from __future__ import annotations

from sentinel.claims import Claim

# The flagship case: $500 shown on the invoice, $5,000,000 actually charged;
# a cloned CEO voice note; a message tone far off the sender's baseline; an
# offshore domain registered 12 days ago; and an embedded prompt injection.
DEMO_DESCRIPTION = (
    "Cloned CEO voice note requesting urgent wire transfer of $5,000,000 to "
    "routing number RT_912000031 at offshore Belize entity via "
    "evilpayments-inc.com. Invoice shows $500 but payload charges $5,000,000."
)
DEMO_AMOUNT = 5_000_000.0


def demo_claims(case_id: str) -> list[Claim]:
    """Return the curated claim set for the flagship demo case.

    These are appended AFTER the real agents run, so — because the reconciler
    keys claims by field and the last write wins — they supply the voice / tone
    signals the live agents can't produce without real audio + a baseline.
    """
    return [
        Claim(
            field="visual_total",
            value=500.0,
            confidence=0.95,
            source_pointer=f"{case_id}/invoice.png#bbox=[410,980,120,40]",
            agent="vision[demo]",
        ),
        Claim(
            field="structured_total",
            value=5_000_000.0,
            confidence=0.99,
            source_pointer=f"{case_id}/data.csv#R14C3",
            agent="finance[demo]",
        ),
        Claim(
            field="tone_anomaly",
            value=0.82,
            confidence=0.80,
            source_pointer=f"{case_id}/message.txt#stylometry",
            agent="stylometric[demo]",
        ),
        Claim(
            field="voice_mismatch",
            value=0.91,
            confidence=0.75,
            source_pointer=f"{case_id}/voicenote.wav#antispoof",
            agent="voice[demo]",
        ),
        Claim(
            field="domain_age_days",
            value=12,
            confidence=0.90,
            source_pointer=f"{case_id}/threat_intel#evilpayments-inc.com",
            agent="threat_intel[demo]",
        ),
        Claim(
            field="injection_present",
            value=True,
            confidence=0.99,
            source_pointer=f"{case_id}/invoice.png#hidden_text",
            agent="injection_scanner[demo]",
        ),
        Claim(
            field="policy_violation",
            value=True,
            confidence=1.0,
            source_pointer=f"{case_id}/policy#matrix",
            agent="policy[demo]",
        ),
    ]
