"""Seed evaluation dataset (build-map ticket #34).

Each case carries the pre-extracted metrics an investigation would have produced,
a ground-truth label (1 = fraud, 0 = legit), and a short rationale. The set is
deliberately built to include the two hard families that separate a real system
from a demo:

  * CONTRADICTION-ONLY FRAUDS — no single agent trips a hard threshold, but the
    cross-examination catches them. These are the frauds the single-model
    baseline MISSES and the contradiction engine CATCHES. Includes the flagship
    case used on camera.

  * FALSE-POSITIVE TRAPS — legitimate but urgent, new-vendor invoices. Superficial
    signals look scary (young domain, high urgency) but the totals match and the
    tone is normal, so a good system must let them through.

This is intentionally small (hand-labeled) and honest about it. Replace/extend
with a larger corpus later; the harness code does not change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Case:
    id: str
    label: int  # 1 fraud, 0 legit
    metrics: dict[str, Any]
    note: str = ""
    family: str = ""  # "contradiction_only" | "obvious_fraud" | "clean" | "fp_trap"
    flagship: bool = False


# The flagship contradiction-only case (build-map #34 / Bible §8.4).
# Every single agent is individually below its hard threshold:
#   ratio = 48000/4800 = 10x ... set just under with 4800 vs 43200 (9x) to be safe
#   tone_anomaly 0.68 (< 0.90 solo), domain 11 days (> 3 solo), no injection.
# Only the COMBINATION crosses the line.
FLAGSHIP = Case(
    id="C-4326",
    label=1,
    family="contradiction_only",
    flagship=True,
    note="Invoice image shows $4,800 (matches a real prior invoice); CSV totals "
         "$43,200; message mimics the CFO except two punctuation habits; domain 11 days old.",
    metrics={
        "visual_total": 4800,
        "structured_total": 43200,   # 9x mismatch -> below the 10x solo threshold
        "tone_anomaly": 0.68,        # anomalous but below the 0.90 solo threshold
        "domain_age_days": 11,       # young but older than the 3-day solo threshold
        "injection_present": False,
    },
)


def seed_dataset() -> list[Case]:
    cases: list[Case] = [FLAGSHIP]

    # --- More contradiction-only frauds (baseline misses, engine catches) ----
    cases += [
        Case("C-4401", 1, {
            "visual_total": 1200, "structured_total": 6000,  # 5x
            "tone_anomaly": 0.66, "domain_age_days": 20,
        }, "Forged total + off-baseline tone + young domain, none extreme alone.",
            family="contradiction_only"),
        Case("C-4402", 1, {
            "visual_total": 9000, "structured_total": 27000,  # 3x
            "tone_anomaly": 0.72, "domain_age_days": 25,
        }, "3x total gap corroborated by tone and domain age.",
            family="contradiction_only"),
        Case("C-4403", 1, {
            "visual_total": 500, "structured_total": 3500,  # 7x
            "voice_mismatch": 0.7, "domain_age_days": 18,
        }, "Cloned-voice note + forged total, neither extreme on its own.",
            family="contradiction_only"),
    ]

    # --- Obvious frauds (both ON and OFF should catch) -----------------------
    cases += [
        Case("C-4501", 1, {
            "visual_total": 400, "structured_total": 6000,  # 15x -> solo hit
            "tone_anomaly": 0.5, "domain_age_days": 40,
        }, "Blatant 15x total mismatch.", family="obvious_fraud"),
        Case("C-4502", 1, {
            "visual_total": 1000, "structured_total": 1000,
            "domain_age_days": 1,  # 1-day domain -> solo hit
            "tone_anomaly": 0.4,
        }, "Brand-new 1-day-old sender domain.", family="obvious_fraud"),
        Case("C-4503", 1, {
            "visual_total": 2000, "structured_total": 2000,
            "injection_present": True,  # injection -> solo hit
        }, "Embedded prompt-injection attempt in the document.", family="obvious_fraud"),
        Case("C-4504", 1, {
            "voice_mismatch": 0.95, "domain_age_days": 60,  # extreme voice -> solo hit
        }, "Extreme voice-spoof score.", family="obvious_fraud"),
    ]

    # --- Clean legitimate cases (both should pass) ---------------------------
    cases += [
        Case("C-5001", 0, {
            "visual_total": 3200, "structured_total": 3200,
            "tone_anomaly": 0.1, "domain_age_days": 1400,
        }, "Established vendor, totals match, normal tone.", family="clean"),
        Case("C-5002", 0, {
            "visual_total": 750, "structured_total": 750,
            "tone_anomaly": 0.2, "domain_age_days": 900,
        }, "Routine small invoice.", family="clean"),
        Case("C-5003", 0, {
            "voice_mismatch": 0.15, "domain_age_days": 2000,
        }, "Genuine voice note from a known colleague.", family="clean"),
    ]

    # --- False-positive traps (legit but superficially scary) ----------------
    cases += [
        Case("C-5101", 0, {
            "visual_total": 12000, "structured_total": 12000,  # totals MATCH
            "tone_anomaly": 0.35, "domain_age_days": 20,  # young domain + urgent
        }, "Urgent end-of-month invoice from a NEW but legitimate vendor.",
            family="fp_trap"),
        Case("C-5102", 0, {
            "visual_total": 8800, "structured_total": 8800,
            "tone_anomaly": 0.45, "domain_age_days": 15,
        }, "New vendor onboarded this month; totals reconcile, tone slightly off.",
            family="fp_trap"),
    ]

    return cases


def flagship_case() -> Case:
    return FLAGSHIP
