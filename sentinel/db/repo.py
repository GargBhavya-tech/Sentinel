"""Database repository — all SQL lives here, nowhere else.

Every function is async and accepts an optional `conn` argument. When `conn`
is None the function borrows one from the shared pool for the duration of
the call. Pass an explicit connection to run multiple operations in one
transaction.

Naming convention:
  create_*   → INSERT, returns the created dataclass.
  update_*   → UPDATE, returns the updated dataclass.
  get_*      → SELECT by primary key, returns dataclass or None.
  list_*     → SELECT multiple rows, returns list of dataclasses.
  save_*     → upsert / bulk write.
  append_*   → audit log only (append-only semantics).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Optional

import psycopg  # type: ignore

from .models import (
    AuditChainEntry,
    AgentResult,
    Case,
    Evidence,
    SynthesizedRule,
)
from .pool import get_db_pool


# ─── helpers ─────────────────────────────────────────────────────────────────

async def _conn():
    """Context manager: borrow a connection from the pool."""
    pool = await get_db_pool()
    return pool.connection()


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


# ─── Cases ───────────────────────────────────────────────────────────────────

async def create_case(
    slack_channel: str,
    slack_ts: str,
    reporter_slack_id: str,
    conn: Optional[psycopg.AsyncConnection] = None,
) -> Case:
    """INSERT a new case in 'created' status and return it."""
    case = Case(
        slack_channel=slack_channel,
        slack_ts=slack_ts,
        reporter_slack_id=reporter_slack_id,
    )
    sql = """
        INSERT INTO cases
            (case_id, slack_channel, slack_ts, reporter_slack_id, status)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING created_at, updated_at
    """
    async with (_conn() if conn is None else _noop(conn)) as c:
        row = await c.fetchone(
            sql,
            (case.case_id, case.slack_channel, case.slack_ts,
             case.reporter_slack_id, case.status),
        )
        case.created_at = row[0]
        case.updated_at = row[1]
    return case


async def update_case_status(
    case_id: str,
    status: str,
    risk_score: Optional[float] = None,
    verdict: Optional[str] = None,
    conn: Optional[psycopg.AsyncConnection] = None,
) -> Case:
    """UPDATE the status (and optionally verdict/risk) on a case."""
    sql = """
        UPDATE cases
        SET status = %s, risk_score = %s, verdict = %s
        WHERE case_id = %s
        RETURNING case_id, slack_channel, slack_ts, reporter_slack_id,
                  status, risk_score, verdict, created_at, updated_at
    """
    async with (_conn() if conn is None else _noop(conn)) as c:
        row = await c.fetchone(sql, (status, risk_score, verdict, case_id))
    if row is None:
        raise LookupError(f"Case {case_id!r} not found")
    return _row_to_case(row)


async def get_case(
    case_id: str,
    conn: Optional[psycopg.AsyncConnection] = None,
) -> Optional[Case]:
    """SELECT one case by primary key — returns None if not found."""
    sql = """
        SELECT case_id, slack_channel, slack_ts, reporter_slack_id,
               status, risk_score, verdict, created_at, updated_at
        FROM cases WHERE case_id = %s
    """
    async with (_conn() if conn is None else _noop(conn)) as c:
        row = await c.fetchone(sql, (case_id,))
    return _row_to_case(row) if row else None


def _row_to_case(row) -> Case:
    return Case(
        case_id=str(row[0]),
        slack_channel=row[1],
        slack_ts=row[2],
        reporter_slack_id=row[3],
        status=row[4],
        risk_score=float(row[5]) if row[5] is not None else None,
        verdict=row[6],
        created_at=row[7],
        updated_at=row[8],
    )


# ─── Evidence ────────────────────────────────────────────────────────────────

async def insert_evidence(
    case_id: str,
    evidence_type: str,
    raw_metrics: dict,
    file_url: Optional[str] = None,
    conn: Optional[psycopg.AsyncConnection] = None,
) -> Evidence:
    ev = Evidence(
        case_id=case_id,
        evidence_type=evidence_type,
        file_url=file_url,
        raw_metrics=raw_metrics,
    )
    sql = """
        INSERT INTO evidence
            (evidence_id, case_id, evidence_type, file_url, raw_metrics)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        RETURNING created_at
    """
    async with (_conn() if conn is None else _noop(conn)) as c:
        row = await c.fetchone(
            sql,
            (ev.evidence_id, ev.case_id, ev.evidence_type,
             ev.file_url, json.dumps(ev.raw_metrics)),
        )
        ev.created_at = row[0]
    return ev


# ─── Agent Results ────────────────────────────────────────────────────────────

async def save_agent_results(
    case_id: str,
    agent_name: str,
    claims: list,
    contradictions: list,
    conn: Optional[psycopg.AsyncConnection] = None,
) -> AgentResult:
    ar = AgentResult(
        case_id=case_id,
        agent_name=agent_name,
        claims=claims,
        contradictions=contradictions,
    )
    sql = """
        INSERT INTO agent_results
            (result_id, case_id, agent_name, claims, contradictions)
        VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)
        RETURNING created_at
    """
    async with (_conn() if conn is None else _noop(conn)) as c:
        row = await c.fetchone(
            sql,
            (ar.result_id, ar.case_id, ar.agent_name,
             json.dumps(ar.claims), json.dumps(ar.contradictions)),
        )
        ar.created_at = row[0]
    return ar


# ─── Audit Chain ─────────────────────────────────────────────────────────────

async def append_audit_event(
    case_id: Optional[str],
    event_type: str,
    payload: dict,
    conn: Optional[psycopg.AsyncConnection] = None,
) -> AuditChainEntry:
    """Append a hash-chained entry to the audit log.

    The entry_hash is SHA-256(prev_hash + event_type + payload_json).
    This makes the chain tamper-evident: editing any past entry breaks all
    subsequent hashes.
    """
    # Get the hash of the last entry in the chain
    sql_prev = "SELECT entry_hash FROM audit_chain ORDER BY entry_id DESC LIMIT 1"
    sql_insert = """
        INSERT INTO audit_chain
            (case_id, event_type, payload, prev_hash, entry_hash)
        VALUES (%s, %s, %s::jsonb, %s, %s)
        RETURNING entry_id, created_at
    """
    async with (_conn() if conn is None else _noop(conn)) as c:
        prev_row = await c.fetchone(sql_prev)
        prev_hash = prev_row[0] if prev_row else ""

        payload_json = json.dumps(payload, sort_keys=True)
        entry_hash = _sha256(prev_hash + event_type + payload_json)

        row = await c.fetchone(
            sql_insert,
            (case_id, event_type, payload_json, prev_hash, entry_hash),
        )
        entry = AuditChainEntry(
            entry_id=row[0],
            case_id=case_id or "",
            event_type=event_type,
            payload=payload,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            created_at=row[1],
        )
    return entry


async def verify_audit_chain(
    conn: Optional[psycopg.AsyncConnection] = None,
) -> tuple[bool, str]:
    """Walk every entry and verify the hash chain is intact.

    Returns (True, "OK") if intact, or (False, explanation) if tampered.
    """
    sql = """
        SELECT entry_id, event_type, payload, prev_hash, entry_hash
        FROM audit_chain ORDER BY entry_id ASC
    """
    async with (_conn() if conn is None else _noop(conn)) as c:
        rows = await c.fetchall(sql)

    running_hash = ""
    for row in rows:
        entry_id, event_type, payload, prev_hash, stored_hash = row
        payload_json = json.dumps(
            payload if isinstance(payload, dict) else json.loads(payload),
            sort_keys=True,
        )
        expected = _sha256(running_hash + event_type + payload_json)
        if stored_hash != expected:
            return False, f"Hash mismatch at entry_id={entry_id}"
        if prev_hash != running_hash:
            return False, f"prev_hash mismatch at entry_id={entry_id}"
        running_hash = stored_hash

    return True, "OK"


# ─── connection context helper ────────────────────────────────────────────────

class _noop:
    """Wrap an already-open connection so 'async with' is a no-op."""
    def __init__(self, conn): self._conn = conn
    async def __aenter__(self): return self._conn
    async def __aexit__(self, *_): pass
