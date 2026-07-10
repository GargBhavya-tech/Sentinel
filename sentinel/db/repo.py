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
from typing import Optional
from contextlib import asynccontextmanager

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


class _ConnAdapter:
    """Give a psycopg3 AsyncConnection the combined execute+fetch helpers this
    module is written against.

    psycopg3 puts `fetchone`/`fetchall` on the cursor, not the connection, and
    they take no SQL. Every repo function here calls `conn.fetchone(sql, params)`
    / `conn.fetchall(sql, params)`, so we wrap the raw connection and run
    execute-then-fetch on a fresh cursor for each call. Commit/rollback is still
    handled by the surrounding `pool.connection()` context manager.
    """

    def __init__(self, conn):
        self._conn = conn

    async def fetchone(self, sql, params=None):
        cur = await self._conn.execute(sql, params or ())
        return await cur.fetchone()

    async def fetchall(self, sql, params=None):
        cur = await self._conn.execute(sql, params or ())
        return await cur.fetchall()

    async def execute(self, sql, params=None):
        return await self._conn.execute(sql, params or ())


@asynccontextmanager
async def _conn():
    """Context manager: borrow a connection from the pool."""
    pool = await get_db_pool()
    async with pool.connection() as c:
        yield _ConnAdapter(c)


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
    async with _conn() if conn is None else _noop(conn) as c:
        row = await c.fetchone(
            sql,
            (
                case.case_id,
                case.slack_channel,
                case.slack_ts,
                case.reporter_slack_id,
                case.status,
            ),
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
    async with _conn() if conn is None else _noop(conn) as c:
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
    async with _conn() if conn is None else _noop(conn) as c:
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
    async with _conn() if conn is None else _noop(conn) as c:
        row = await c.fetchone(
            sql,
            (
                ev.evidence_id,
                ev.case_id,
                ev.evidence_type,
                ev.file_url,
                json.dumps(ev.raw_metrics),
            ),
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
    async with _conn() if conn is None else _noop(conn) as c:
        row = await c.fetchone(
            sql,
            (
                ar.result_id,
                ar.case_id,
                ar.agent_name,
                json.dumps(ar.claims),
                json.dumps(ar.contradictions),
            ),
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
    async with _conn() if conn is None else _noop(conn) as c:
        # Serialize appends across concurrent investigations. Without this,
        # two writers read the SAME prev_hash and fork the chain, which makes
        # verify_audit_chain() report tampering (prev_hash mismatch). The
        # transaction-scoped advisory lock is released automatically on commit
        # (i.e. when the pool.connection() block exits).
        #
        # The lock MUST be global (this fixed key), NOT per-case: the chain is a
        # single global sequence (sql_prev reads the last entry across ALL
        # cases, and verify_audit_chain walks every entry in entry_id order). A
        # per-case lock would let two different cases read the same global tip
        # concurrently and fork the chain — reintroducing the exact bug this
        # prevents. Appends are sub-millisecond, so the convoy cost is negligible
        # next to the tamper-evidence guarantee.
        _AUDIT_CHAIN_LOCK_KEY = 911017
        await c.execute("SELECT pg_advisory_xact_lock(%s)", (_AUDIT_CHAIN_LOCK_KEY,))
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
    async with _conn() if conn is None else _noop(conn) as c:
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


# ─── Synthesized Rules ────────────────────────────────────────────────────


async def save_rule(
    rule,  # sentinel.rules.schema.Rule
    conn: Optional[psycopg.AsyncConnection] = None,
) -> SynthesizedRule:
    """INSERT a synthesized rule (always starts as shadow)."""
    sql = """
        INSERT INTO synthesized_rules
            (rule_id, source_case_id, rule_json, status)
        VALUES (%s, %s, %s::jsonb, %s)
        RETURNING created_at
    """
    async with _conn() if conn is None else _noop(conn) as c:
        row = await c.fetchone(
            sql,
            (
                rule.rule_id,
                rule.source_case_id,
                json.dumps(rule.to_dict()),
                rule.status,
            ),
        )
    sr = SynthesizedRule(
        rule_id=rule.rule_id,
        source_case_id=rule.source_case_id,
        rule_json=rule.to_dict(),
        status=rule.status,
    )
    if row:
        sr.created_at = row[0]
    return sr


async def list_rules(
    status: Optional[str] = None,
    conn: Optional[psycopg.AsyncConnection] = None,
) -> list[SynthesizedRule]:
    """SELECT all rules, optionally filtered by status ('shadow' or 'enforced')."""
    if status:
        sql = """
            SELECT rule_id, source_case_id, rule_json, status, created_at
            FROM synthesized_rules WHERE status = %s ORDER BY created_at DESC
        """
        params: tuple = (status,)
    else:
        sql = """
            SELECT rule_id, source_case_id, rule_json, status, created_at
            FROM synthesized_rules ORDER BY created_at DESC
        """
        params = ()
    async with _conn() if conn is None else _noop(conn) as c:
        rows = await c.fetchall(sql, params)
    return [
        SynthesizedRule(
            rule_id=str(r[0]),
            source_case_id=str(r[1]),
            rule_json=r[2] if isinstance(r[2], dict) else json.loads(r[2]),
            status=r[3],
            created_at=r[4],
        )
        for r in (rows or [])
    ]


async def promote_rule(
    rule_id: str,
    conn: Optional[psycopg.AsyncConnection] = None,
) -> SynthesizedRule:
    """UPDATE a shadow rule to enforced status."""
    sql = """
        UPDATE synthesized_rules
        SET status = 'enforced'
        WHERE rule_id = %s
        RETURNING rule_id, source_case_id, rule_json, status, created_at
    """
    async with _conn() if conn is None else _noop(conn) as c:
        row = await c.fetchone(sql, (rule_id,))
    if row is None:
        raise LookupError(f"Rule {rule_id!r} not found")
    return SynthesizedRule(
        rule_id=str(row[0]),
        source_case_id=str(row[1]),
        rule_json=row[2] if isinstance(row[2], dict) else json.loads(row[2]),
        status=row[3],
        created_at=row[4],
    )



# ─── List Cases ──────────────────────────────────────────────────────────────


async def list_cases(
    limit: int = 20,
    conn=None,
) -> list[Case]:
    """SELECT the most recent cases ordered by created_at DESC."""
    sql = """
        SELECT case_id, slack_channel, slack_ts, reporter_slack_id,
               status, risk_score, verdict, created_at, updated_at
        FROM cases
        ORDER BY created_at DESC
        LIMIT %s
    """
    async with _conn() if conn is None else _noop(conn) as c:
        rows = await c.fetchall(sql, (limit,))
    return [_row_to_case(r) for r in (rows or [])]


# ─── Audit Chain for a Case ───────────────────────────────────────────────────


async def get_audit_chain(
    case_id: str,
    conn=None,
) -> list[dict]:
    """Return all audit entries for a specific case."""
    sql = """
        SELECT entry_id, case_id, event_type, payload, prev_hash, entry_hash, created_at
        FROM audit_chain
        WHERE case_id = %s
        ORDER BY entry_id ASC
    """
    async with _conn() if conn is None else _noop(conn) as c:
        rows = await c.fetchall(sql, (case_id,))
    result = []
    for r in (rows or []):
        result.append({
            "entry_id": r[0],
            "case_id": str(r[1]),
            "event_type": r[2],
            "payload": r[3] if isinstance(r[3], dict) else {},
            "prev_hash": r[4][:16] + "…" if r[4] else "",
            "entry_hash": r[5][:16] + "…" if r[5] else "",
            "created_at": str(r[6]) if r[6] else "",
        })
    return result


# ─── connection context helper ────────────────────────────────────────────────


class _noop:
    """Wrap an already-open connection so 'async with' is a no-op.

    Yields the same execute+fetch adapter as `_conn()` so repo functions behave
    identically whether they borrow from the pool or reuse a caller's
    connection. If an adapter is passed in, it's used as-is.
    """

    def __init__(self, conn):
        self._conn = conn if isinstance(conn, _ConnAdapter) else _ConnAdapter(conn)

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_):
        pass
