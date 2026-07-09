"""Sentinel — a Slack-native fraud investigator whose agents cross-examine.

Phase 0 (implemented): async Slack gateway (FastAPI + Bolt), PostgreSQL case
lifecycle, and a local NetworkX graph cache fed by Slack's Event API.

Phase 1–3 spine (implemented): symbolic contradiction reconciler, mock
specialist agents, and the evaluation harness.

Phase 2 (next): real LLM-backed specialist agents, PII gateway, file forensics.
"""

from .claims import Claim, Contradiction, Verdict
from .pipeline import run_case
from .reconciler import reconcile

__all__ = ["Claim", "Contradiction", "Verdict", "run_case", "reconcile"]
__version__ = "0.1.0"
