"""In-memory repository — runs without PostgreSQL for local demos.

Activated when DATABASE_URL=memory:// in .env.
Provides the same async API as the real psycopg-backed repo.py so all
callers (gateway, sse_worker, etc.) work identically.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

# ── In-memory stores ──────────────────────────────────────────────────────────
_cases: dict[str, dict] = {}
_agent_results: list[dict] = []
_audit_chain: list[dict] = []
_rules: dict[str, dict] = {}
_audit_lock = asyncio.Lock()

# ── Fake Case dataclass ───────────────────────────────────────────────────────

@dataclass
class Case:
    case_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    slack_channel: str = "C_DEMO"
    slack_ts: str = ""
    reporter_slack_id: str = "U_DEMO"
    status: str = "created"
    risk_score: Optional[float] = None
    verdict: Optional[str] = None
    created_at: Any = None
    updated_at: Any = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.updated_at is None:
            self.updated_at = self.created_at
        if not self.slack_ts:
            self.slack_ts = str(time.time())

@dataclass
class AgentResult:
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str = ""
    agent_name: str = ""
    claims: list = field(default_factory=list)
    contradictions: list = field(default_factory=list)
    created_at: Any = None

@dataclass
class Evidence:
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str = ""
    evidence_type: str = ""
    file_url: Optional[str] = None
    raw_metrics: dict = field(default_factory=dict)
    created_at: Any = None

@dataclass
class AuditChainEntry:
    entry_id: int = 0
    case_id: str = ""
    event_type: str = ""
    payload: dict = field(default_factory=dict)
    prev_hash: str = ""
    entry_hash: str = ""
    created_at: Any = None

@dataclass
class SynthesizedRule:
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_case_id: str = ""
    rule_json: dict = field(default_factory=dict)
    status: str = "shadow"
    created_at: Any = None
    # Convenience attributes used by gateway
    description: str = ""
    conditions: dict = field(default_factory=dict)


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# ── Cases ──────────────────────────────────────────────────────────────────────

async def create_case(slack_channel="C_DEMO", slack_ts="", reporter_slack_id="U_DEMO", conn=None) -> Case:
    c = Case(slack_channel=slack_channel, slack_ts=slack_ts or str(uuid.uuid4()), reporter_slack_id=reporter_slack_id)
    _cases[c.case_id] = {
        "case_id": c.case_id, "slack_channel": c.slack_channel,
        "slack_ts": c.slack_ts, "reporter_slack_id": c.reporter_slack_id,
        "status": c.status, "risk_score": None, "verdict": None,
        "created_at": c.created_at, "updated_at": c.updated_at,
    }
    return c

async def update_case_status(case_id, status, risk_score=None, verdict=None, conn=None) -> Case:
    if case_id not in _cases:
        _cases[case_id] = {"case_id": case_id, "status": status, "risk_score": risk_score, "verdict": verdict, "created_at": time.time(), "updated_at": time.time()}
    else:
        _cases[case_id].update({"status": status, "risk_score": risk_score, "verdict": verdict, "updated_at": time.time()})
    d = _cases[case_id]
    return Case(case_id=d["case_id"], slack_channel=d.get("slack_channel", "C_DEMO"), slack_ts=d.get("slack_ts", ""), reporter_slack_id=d.get("reporter_slack_id", "U_DEMO"), status=d["status"], risk_score=d["risk_score"], verdict=d["verdict"])

async def get_case(case_id, conn=None) -> Optional[Case]:
    d = _cases.get(case_id)
    if not d:
        return None
    return Case(**{k: d[k] for k in ("case_id", "slack_channel", "slack_ts", "reporter_slack_id", "status", "risk_score", "verdict", "created_at", "updated_at")})

async def list_cases(limit=20, conn=None) -> list[Case]:
    all_cases = sorted(_cases.values(), key=lambda c: c.get("created_at", 0), reverse=True)
    return [Case(**{k: d[k] for k in ("case_id", "slack_channel", "slack_ts", "reporter_slack_id", "status", "risk_score", "verdict", "created_at", "updated_at")}) for d in all_cases[:limit]]

# ── Evidence ───────────────────────────────────────────────────────────────────

async def insert_evidence(case_id, evidence_type, raw_metrics, file_url=None, conn=None) -> Evidence:
    ev = Evidence(case_id=case_id, evidence_type=evidence_type, file_url=file_url, raw_metrics=raw_metrics, created_at=time.time())
    return ev

# ── Agent Results ──────────────────────────────────────────────────────────────

async def save_agent_results(case_id, agent_name, claims, contradictions, conn=None) -> AgentResult:
    ar = AgentResult(case_id=case_id, agent_name=agent_name, claims=claims, contradictions=contradictions, created_at=time.time())
    _agent_results.append({"case_id": case_id, "agent_name": agent_name})
    return ar

# ── Audit Chain ────────────────────────────────────────────────────────────────

async def append_audit_event(case_id, event_type, payload, conn=None) -> AuditChainEntry:
    async with _audit_lock:
        prev_hash = _audit_chain[-1]["entry_hash"] if _audit_chain else ""
        payload_json = json.dumps(payload, sort_keys=True)
        entry_hash = _sha256(prev_hash + event_type + payload_json)
        entry_id = len(_audit_chain) + 1
        entry = {
            "entry_id": entry_id, "case_id": case_id or "", "event_type": event_type,
            "payload": payload, "prev_hash": prev_hash, "entry_hash": entry_hash,
            "created_at": time.time(),
        }
        _audit_chain.append(entry)
        return AuditChainEntry(entry_id=entry_id, case_id=case_id or "", event_type=event_type, payload=payload, prev_hash=prev_hash, entry_hash=entry_hash, created_at=entry["created_at"])

async def verify_audit_chain(conn=None) -> tuple[bool, str]:
    running = ""
    for e in _audit_chain:
        payload_json = json.dumps(e["payload"], sort_keys=True)
        expected = _sha256(running + e["event_type"] + payload_json)
        if e["entry_hash"] != expected:
            return False, f"Hash mismatch at entry_id={e['entry_id']}"
        if e["prev_hash"] != running:
            return False, f"prev_hash mismatch at entry_id={e['entry_id']}"
        running = e["entry_hash"]
    return True, "OK"

async def get_audit_chain(case_id, conn=None) -> list[dict]:
    return [
        {
            "entry_id": e["entry_id"], "case_id": e["case_id"], "event_type": e["event_type"],
            "payload": e["payload"],
            "prev_hash": e["prev_hash"][:16] + "…" if e["prev_hash"] else "",
            "entry_hash": e["entry_hash"][:16] + "…" if e["entry_hash"] else "",
            "created_at": str(e["created_at"]),
        }
        for e in _audit_chain if e["case_id"] == case_id
    ]

# ── Rules ──────────────────────────────────────────────────────────────────────

async def save_rule(rule, conn=None) -> SynthesizedRule:
    d = rule.to_dict() if hasattr(rule, "to_dict") else {}
    _rules[rule.rule_id] = {
        "rule_id": rule.rule_id, "source_case_id": getattr(rule, "source_case_id", ""),
        "rule_json": d, "status": rule.status,
        "description": getattr(rule, "description", d.get("description", "")),
        "conditions": getattr(rule, "conditions", d.get("conditions", {})),
        "created_at": time.time(),
    }
    return SynthesizedRule(rule_id=rule.rule_id, source_case_id=getattr(rule, "source_case_id", ""), rule_json=d, status=rule.status, description=getattr(rule, "description", ""))

async def list_rules(status=None, conn=None) -> list[SynthesizedRule]:
    rules = list(_rules.values())
    if status:
        rules = [r for r in rules if r["status"] == status]
    rules.sort(key=lambda r: r.get("created_at", 0), reverse=True)
    return [SynthesizedRule(rule_id=r["rule_id"], source_case_id=r.get("source_case_id", ""), rule_json=r.get("rule_json", {}), status=r["status"], description=r.get("description", ""), created_at=r.get("created_at")) for r in rules]

async def promote_rule(rule_id, conn=None) -> SynthesizedRule:
    if rule_id not in _rules:
        raise LookupError(f"Rule {rule_id!r} not found")
    _rules[rule_id]["status"] = "enforced"
    r = _rules[rule_id]
    return SynthesizedRule(rule_id=r["rule_id"], source_case_id=r.get("source_case_id", ""), rule_json=r.get("rule_json", {}), status="enforced", description=r.get("description", ""))

# ── Pool stubs (no-op for in-memory mode) ─────────────────────────────────────

async def get_db_pool():
    return None

async def close_db_pool():
    pass
