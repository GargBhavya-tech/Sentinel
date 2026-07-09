"""Structured claims — the contract between agents and the reconciler.

Every specialist agent (Vision, Finance, Stylometric, Voice, ...) is forced to
emit its finding as a `Claim`: a value, how confident it is, and a pointer back
to the exact evidence that produced it. The reconciler (see reconciler.py) then
reasons over these claims *deterministically* — no LLM in the decision path.

The `source_pointer` is what powers the "click-to-source" provenance UI later:
click a claim in the verdict, jump to the pixel / CSV cell / transcript token.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Claim:
    """One structured assertion from one agent."""

    field: str  # e.g. "visual_total", "tone_anomaly", "domain_age_days"
    value: Any  # numeric or bool
    confidence: float  # 0..1, how sure the proposing agent is
    source_pointer: str  # e.g. "invoice.png#bbox=[x,y,w,h]" or "data.csv#R14C3"
    agent: str  # which agent proposed it

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be in [0,1], got {self.confidence} for {self.field}"
            )


@dataclass
class Contradiction:
    """A single axis of cross-examination that fired."""

    axis: str  # "visual_vs_structured" | "tone_vs_baseline" | "voice_vs_baseline" | "injection"
    detail: str  # human-readable explanation for the Slack card
    weight: float  # contribution to overall risk (0..1)
    evidence: list[str] = field(default_factory=list)  # source_pointers -> click-to-source


@dataclass
class Verdict:
    """The reconciler's output for one case."""

    risk: float  # 0..1
    verdict: str  # "FRAUD_LIKELY" | "REVIEW" | "CLEAR"
    contradictions: list[Contradiction] = field(default_factory=list)
    counterfactual: Optional[str] = None  # "would be CLEAR if domain > 90d AND totals matched"

    @property
    def is_flagged(self) -> bool:
        """True if the case is not CLEAR (used by the eval harness)."""
        return self.verdict != "CLEAR"
