"""Sentinel — a Slack-native fraud investigator whose agents cross-examine.

This package currently implements the CORE spine (build-map tickets #15 and #34):
the symbolic contradiction reconciler and the evaluation harness. Slack, the
specialist LLM agents, RTS graph, and UI are wired around this core later.
"""

from .claims import Claim, Contradiction, Verdict
from .pipeline import run_case
from .reconciler import reconcile

__all__ = ["Claim", "Contradiction", "Verdict", "run_case", "reconcile"]
__version__ = "0.1.0"
