"""Python dataclasses mirroring the DB tables.

No ORM — plain dataclasses + plain SQL so the data model is readable line
by line, easy to audit, and trivially serialisable to the Slack Block Kit
cards and the React console.

Every table has a matching dataclass here. The repo (repo.py) is the only
place that does SQL; nothing else touches the DB directly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# ─── helpers ─────────────────────────────────────────────────────────────────


def _now() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ─── Case ────────────────────────────────────────────────────────────────────

CASE_STATUS = ("created", "analyzing", "verdict", "resolved")


@dataclass
class Case:
    """One investigation triggered by @Sentinel investigate."""

    case_id: str = field(default_factory=_uuid)
    slack_channel: str = ""  # C0123456789
    slack_ts: str = ""  # message timestamp used for threading
    reporter_slack_id: str = ""  # U0123456789
    status: str = "created"  # created → analyzing → verdict → resolved
    risk_score: Optional[float] = None
    verdict: Optional[str] = None  # FRAUD_LIKELY | REVIEW | CLEAR
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if self.status not in CASE_STATUS:
            raise ValueError(
                f"status must be one of {CASE_STATUS}, got {self.status!r}"
            )


# ─── Evidence ────────────────────────────────────────────────────────────────

EVIDENCE_TYPES = ("file", "message", "voice", "url")


@dataclass
class Evidence:
    """One piece of uploaded evidence attached to a case."""

    evidence_id: str = field(default_factory=_uuid)
    case_id: str = ""
    evidence_type: str = "file"  # file | message | voice | url
    file_url: Optional[str] = None  # Slack CDN URL if a file
    raw_metrics: dict[str, Any] = field(
        default_factory=dict
    )  # pre-extracted metrics JSONB
    created_at: datetime = field(default_factory=_now)


# ─── AgentResult ─────────────────────────────────────────────────────────────


@dataclass
class AgentResult:
    """The structured output from one specialist agent for one case."""

    result_id: str = field(default_factory=_uuid)
    case_id: str = ""
    agent_name: str = ""  # "vision" | "finance" | "stylometric" | …
    claims: list[dict] = field(default_factory=list)  # serialised Claim objects
    contradictions: list[dict] = field(
        default_factory=list
    )  # serialised Contradiction objects
    created_at: datetime = field(default_factory=_now)


# ─── SynthesizedRule ─────────────────────────────────────────────────────────


@dataclass
class SynthesizedRule:
    """A detection rule auto-written from a confirmed fraud case (ticket #26)."""

    rule_id: str = field(default_factory=_uuid)
    source_case_id: str = ""
    rule_json: dict[str, Any] = field(default_factory=dict)  # structured JSON rule
    status: str = "shadow"  # shadow → enforced
    created_at: datetime = field(default_factory=_now)


# ─── AuditChainEntry ─────────────────────────────────────────────────────────


@dataclass
class AuditChainEntry:
    """One entry in the hash-chained audit log (ticket #27).

    `entry_id` is a BIGSERIAL from Postgres — set to 0 before insert, then
    updated by the repo after the INSERT returns the generated id.
    `prev_hash` and `entry_hash` are computed by the repo layer.
    """

    entry_id: int = 0
    case_id: str = ""
    event_type: str = (
        ""  # "case_created" | "verdict" | "quarantine" | "rule_promoted" …
    )
    payload: dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""  # SHA-256 of the previous entry (hex)
    entry_hash: str = ""  # SHA-256 of this entry's canonical form (hex)
    created_at: datetime = field(default_factory=_now)
