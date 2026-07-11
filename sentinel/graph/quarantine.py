"""Active Quarantine — build-map ticket #22.

A one-click "[Quarantine]" action that:
  1. Records which nodes (user/file/channel) have been quarantined and why.
  2. Writes an audit entry for each quarantine action (links to audit chain #27).
  3. Is exposed via the MCP `quarantine` tool so Slack's action button can
     trigger it without a direct DB call.

Build-map spec: "A one-click 'Quarantine' button that redacts the payload
from the localized instances found by #19, logged to the audit chain."

Architecture
------------
- In-memory quarantine log (list of QuarantineEntry).
- `quarantine()` is idempotent: re-quarantining an already-quarantined node
  is a no-op (returns the existing entry).
- `is_quarantined(node_id)` for fast gate checks.
- The log is designed to be flushed to the DB audit chain once Postgres is
  wired in live deployment.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)


# ── Quarantine log (in-memory) ────────────────────────────────────────────────

@dataclass
class QuarantineEntry:
    entry_id: str
    case_id: str
    node_id: str
    node_type: str          # "user" | "channel" | "file" | "unknown"
    reason: str
    quarantined_by: str     # Slack user ID of the analyst who clicked the button
    quarantined_at: datetime
    lifted_at: Optional[datetime] = None
    audit_note: str = ""

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "case_id": self.case_id,
            "node_id": self.node_id,
            "node_type": self.node_type,
            "reason": self.reason,
            "quarantined_by": self.quarantined_by,
            "quarantined_at": self.quarantined_at.isoformat(),
            "lifted_at": self.lifted_at.isoformat() if self.lifted_at else None,
            "audit_note": self.audit_note,
        }


@dataclass
class QuarantineResult:
    quarantined: list[QuarantineEntry] = field(default_factory=list)
    already_quarantined: list[str] = field(default_factory=list)
    case_id: str = ""

    @property
    def total_new(self) -> int:
        return len(self.quarantined)

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "total_new": self.total_new,
            "already_quarantined_count": len(self.already_quarantined),
            "quarantined": [e.to_dict() for e in self.quarantined],
            "already_quarantined": self.already_quarantined,
        }


# ── In-memory state ───────────────────────────────────────────────────────────

_log: list[QuarantineEntry] = []
_quarantined_nodes: dict[str, QuarantineEntry] = {}   # node_id → entry


def clear_log() -> None:
    """Clear the quarantine log (for tests)."""
    _log.clear()
    _quarantined_nodes.clear()


# ── Public API ─────────────────────────────────────────────────────────────────

def quarantine(
    case_id: str,
    node_ids: list[str],
    reason: str,
    quarantined_by: str = "system",
) -> QuarantineResult:
    """Quarantine one or more nodes.

    Parameters
    ----------
    case_id:        The Sentinel case that triggered the quarantine.
    node_ids:       List of Slack node IDs (users, channels, files) to quarantine.
    reason:         Human-readable reason, logged to audit chain.
    quarantined_by: Slack user ID of the analyst, or "system" for auto.

    Returns
    -------
    QuarantineResult
        Newly quarantined entries + list of already-quarantined IDs (idempotent).
    """
    from .cache import get_graph

    G = get_graph()
    now = datetime.now(timezone.utc)
    newly_quarantined: list[QuarantineEntry] = []
    already: list[str] = []

    for node_id in node_ids:
        if node_id in _quarantined_nodes:
            already.append(node_id)
            log.debug("quarantine: %s already quarantined — skip", node_id)
            continue

        attrs = G.nodes.get(node_id, {})
        node_type = attrs.get("node_type", "unknown")

        entry = QuarantineEntry(
            entry_id=str(uuid.uuid4()),
            case_id=case_id,
            node_id=node_id,
            node_type=node_type,
            reason=reason,
            quarantined_by=quarantined_by,
            quarantined_at=now,
            audit_note=(
                f"QUARANTINE: {node_type} {node_id} quarantined by "
                f"{quarantined_by} for case {case_id}: {reason}"
            ),
        )

        _log.append(entry)
        _quarantined_nodes[node_id] = entry
        newly_quarantined.append(entry)

        log.info(
            "quarantine: %s (%s) quarantined for case=%s by=%s reason=%r",
            node_id, node_type, case_id, quarantined_by, reason,
        )

    return QuarantineResult(
        quarantined=newly_quarantined,
        already_quarantined=already,
        case_id=case_id,
    )


def lift_quarantine(node_id: str, lifted_by: str = "analyst") -> bool:
    """Lift the quarantine on a node. Returns True if it was quarantined."""
    if node_id not in _quarantined_nodes:
        return False
    entry = _quarantined_nodes.pop(node_id)
    entry.lifted_at = datetime.now(timezone.utc)
    log.info("quarantine: %s lifted by %s", node_id, lifted_by)
    return True


def is_quarantined(node_id: str) -> bool:
    """Fast gate check — is this node currently quarantined?"""
    return node_id in _quarantined_nodes


def get_quarantine_log() -> list[dict]:
    """Return the full quarantine log as a list of dicts."""
    return [e.to_dict() for e in _log]


def get_quarantine_entry(node_id: str) -> Optional[QuarantineEntry]:
    """Return the active quarantine entry for a node, or None."""
    return _quarantined_nodes.get(node_id)
