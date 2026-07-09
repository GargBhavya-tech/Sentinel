"""Adversarial Self-Play Agent (build-map ticket #17).

Sentinel generates the strongest fake it can of the current document type,
then checks whether its own detector catches it, and reports the result.
"""

from __future__ import annotations

import logging
from typing import Any
from sentinel.claims import Claim
from sentinel.pipeline import run_case

log = logging.getLogger(__name__)


def generate_sophisticated_fake(document_type: str = "invoice") -> list[Claim]:
    """Generate a set of claims representing a sophisticated deepfake."""
    if document_type == "invoice":
        # A fake invoice where the attacker perfectly matched the visual logo
        # but altered the underlying structured total, and used a newly registered domain.
        return [
            Claim(
                agent="vision",
                field="visual_total",
                value=15000.00,
                confidence=0.95,
                source_pointer="page1_header",
            ),
            Claim(
                agent="finance",
                field="structured_total",
                value=45000.00,
                confidence=0.99,
                source_pointer="csv_export",
            ),
            Claim(
                agent="threat_intel",
                field="domain_age_days",
                value=1,
                confidence=1.0,
                source_pointer="whois",
            ),
            Claim(
                agent="stylometric",
                field="tone_anomaly",
                value=0.1,
                confidence=0.8,
                source_pointer="email_body",
            ),  # Stylometrically perfect
        ]
    elif document_type == "voice_note":
        # A deepfake voice note where the audio sounds perfect (low voice mismatch)
        # but the linguistic tone is highly anomalous compared to the user's history.
        return [
            Claim(
                agent="voice",
                field="voice_mismatch",
                value=0.05,
                confidence=0.95,
                source_pointer="audio_model",
            ),  # Audio passes
            Claim(
                agent="stylometric",
                field="tone_anomaly",
                value=0.92,
                confidence=0.90,
                source_pointer="transcript",
            ),  # But they don't speak like this
            Claim(
                agent="threat_intel",
                field="domain_age_days",
                value=999,
                confidence=1.0,
                source_pointer="n/a",
            ),
        ]
    return []


def run_self_play(document_type: str = "invoice") -> dict[str, Any]:
    """Run the self-play loop and see if the engine catches the fake."""
    log.info(f"Initiating Adversarial Self-Play for {document_type}...")

    # 1. Generate fake
    fake_claims = generate_sophisticated_fake(document_type)

    # 2. Test against own contradiction engine
    verdict = run_case(claims=fake_claims)

    # 3. Evaluate result
    passed = verdict.verdict == "FRAUD_LIKELY"

    result = {
        "document_type": document_type,
        "fake_claims_generated": len(fake_claims),
        "caught_by_engine": passed,
        "verdict_returned": verdict.verdict,
        "contradictions_found": [c.axis for c in verdict.contradictions],
    }

    if passed:
        log.info(
            "Self-Play Result: SUCCESS. Sentinel successfully caught its own deepfake."
        )
    else:
        log.warning("Self-Play Result: FAILED. Sentinel missed the fake.")

    return result
