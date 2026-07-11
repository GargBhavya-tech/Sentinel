"""SSE Investigation Worker — streaming bridge between backend and React console.

This is the out-of-band worker adapted for Server-Sent Events. Instead of
posting results to Slack threads, it pushes structured JSON events into an
asyncio.Queue that the /api/investigate/{case_id}/stream SSE endpoint drains.

Event sequence per investigation
---------------------------------
  case_created          → {case_id, status}
  temporal_recall       → {similar_cases}
  agents_started        → {agent_list}
  agent_complete        → {agent_name, status, claims, elapsed_ms}  (one per agent)
  silence_triggered     → {reason, missing}         ← ticket #18
  contradiction_result  → {axes, risk, verdict}
  blast_radius          → {nodes, edges, summary}
  rule_synthesized      → {rule_id, description, status}
  federation_check      → {matches, simulated}      ← ticket #29
  compliance_check      → {should_file_sar, answer, citations}  ← ticket #13
  honeypot_result       → {dialogue, tracking_token} ← ticket #25 (FRAUD_LIKELY only)
  expected_loss         → {amount_at_risk, risk, expected_loss}  ← ticket #24
  verdict               → {verdict, risk, contradictions, counterfactual, metrics}
  stream_end            → {case_id}

All events are JSON-encoded and pushed via asyncio.Queue[dict | None].
None is the sentinel value that signals end-of-stream.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict
from typing import Any

from sentinel.db import repo
from sentinel.pipeline import run_case
from sentinel.agents import (
    vision_agent,
    finance_agent,
    stylometric_agent,
    voice_agent,
    threat_intel_agent,
    nlp_agent,
    policy_agent,
)
from sentinel.agents.compliance_agent import analyze as compliance_analyze
from sentinel.agents.red_team_agent import generate_defense
from sentinel.agents.adversarial_agent import run_self_play
from sentinel.agents.honeypot_agent import run_honeypot
from sentinel.claims import Claim
from sentinel.agents.harvest import harvest_claims
from sentinel.ingest import download_evidence, cleanup_evidence
from sentinel.rules.synthesizer import synthesize_rule
from sentinel.rules.schema import Rule
import re as _re

# First bare domain in free text — lets threat-intel scan the REAL domain in the
# report instead of the old hardcoded "example.com" placeholder.
_DOMAIN_RE = _re.compile(
    r"\b([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.(?:[a-z]{2,}))\b", _re.IGNORECASE
)
from sentinel.recall import recall as temporal_recall
from sentinel.federated import check_federation
from sentinel.eval.active_learning import register_case_score

log = logging.getLogger(__name__)

# ── In-memory queue registry ───────────────────────────────────────────────────
# Maps case_id → asyncio.Queue so the SSE endpoint can drain it
_queues: dict[str, asyncio.Queue] = {}


def create_case_queue(case_id: str) -> asyncio.Queue:
    """Create and register an event queue for a case."""
    q: asyncio.Queue = asyncio.Queue()
    _queues[case_id] = q
    return q


def get_case_queue(case_id: str) -> asyncio.Queue | None:
    return _queues.get(case_id)


def cleanup_case_queue(case_id: str) -> None:
    _queues.pop(case_id, None)


# ── Event helpers ──────────────────────────────────────────────────────────────

async def _emit(q: asyncio.Queue, event_type: str, data: dict) -> None:
    payload = {"event": event_type, "data": data, "ts": time.time()}
    await q.put(payload)
    log.debug("SSE emit: %s %s", event_type, str(data)[:120])


# ── Expected-Loss Triage (#24) ─────────────────────────────────────────────────

def _compute_expected_loss(
    risk: float,
    amount_at_risk: float,
) -> dict:
    """Compute expected loss and attacker ROI teardown (ticket #24)."""
    expected_loss = risk * amount_at_risk

    # Attacker ROI estimation (simplified model for demo)
    setup_cost_estimate = max(200, amount_at_risk * 0.002)    # ~0.2% setup cost
    attacker_payout = amount_at_risk * 0.85                    # typical recovery rate ~15%
    attacker_roi = (attacker_payout - setup_cost_estimate) / setup_cost_estimate

    return {
        "amount_at_risk": round(amount_at_risk, 2),
        "risk_probability": round(risk, 3),
        "expected_loss": round(expected_loss, 2),
        "attacker_economics": {
            "estimated_setup_cost": round(setup_cost_estimate, 2),
            "estimated_payout": round(attacker_payout, 2),
            "attacker_roi_x": round(attacker_roi, 1),
        },
        "triage_priority": (
            "CRITICAL" if expected_loss > 100_000
            else "HIGH" if expected_loss > 10_000
            else "MEDIUM" if expected_loss > 1_000
            else "LOW"
        ),
    }


# ── Confidence-Calibrated Silence (#18) ───────────────────────────────────────

def _check_silence(claims: list[Claim]) -> tuple[bool, str]:
    """Return (should_silence, reason) — True if evidence is too thin."""
    non_null_claims = [c for c in claims if c.value is not None]
    if len(non_null_claims) < 2:
        missing = _missing_modalities(claims)
        ask = (
            " I have "
            + (", ".join(_present_modalities(claims)) or "nothing usable")
            + ". To cross-examine, send me "
            + " or ".join(missing[:3])
            + "."
        )
        return True, (
            "Insufficient evidence: fewer than 2 agents returned usable signal. "
            "Sentinel needs at least two independent modalities to cross-examine."
            + ask
        )
    return False, ""


# Which contradiction-relevant modalities produced a usable signal.
_MODALITY_FIELDS = {
    "the invoice/document total": ("visual_total", "structured_total"),
    "a voice note": ("voice_mismatch",),
    "a writing sample for the sender": ("tone_anomaly",),
    "the sender domain": ("domain_age_days",),
}


def _present_modalities(claims: list[Claim]) -> list[str]:
    present_fields = {c.field for c in claims if c.value is not None}
    return [
        label
        for label, fields in _MODALITY_FIELDS.items()
        if present_fields.intersection(fields)
    ]


def _missing_modalities(claims: list[Claim]) -> list[str]:
    present_fields = {c.field for c in claims if c.value is not None}
    return [
        label
        for label, fields in _MODALITY_FIELDS.items()
        if not present_fields.intersection(fields)
    ]


# ── Main SSE investigation worker ──────────────────────────────────────────────

async def investigate_streaming(
    case_id: str,
    q: asyncio.Queue,
    event_text: str = "invoice fraud",
    amount_at_risk: float = 0.0,
    channel: str = "C_DEMO",
    reporter: str = "U_DEMO",
    file_url: str | None = None,
    demo_case: bool = False,
) -> None:
    """Run the full Sentinel investigation, emitting SSE events into q.

    Parameters
    ----------
    case_id : str
        Pre-created case UUID.
    q : asyncio.Queue
        The event queue the SSE endpoint is draining.
    event_text : str
        Free-text description of the suspicious activity.
    amount_at_risk : float
        Dollar amount at risk (for expected-loss triage).
    channel : str
        Slack channel ID (or "C_DEMO" for the React console path).
    reporter : str
        Slack user ID who triggered the investigation.
    """
    evidence_path: str | None = None  # temp file, cleaned up in finally
    try:
        short_id = case_id[:8]
        log.info("SSE worker started for case %s", short_id)

        # ── 1. Case created ───────────────────────────────────────────────────
        await _emit(q, "case_created", {
            "case_id": case_id,
            "short_id": short_id,
            "status": "analyzing",
            "channel": channel,
            "reporter": reporter,
        })

        await repo.append_audit_event(
            case_id=case_id,
            event_type="case_created",
            payload={"channel": channel, "reporter": reporter, "text": event_text[:200]},
        )

        # ── 2. Temporal recall runs AFTER agents (see step 4b) ────────────────
        # An empty claims_dict embeds to the zero vector and can never match a
        # prior case, so recall is deferred until the real claims exist.

        # ── 3. Announce agents ────────────────────────────────────────────────
        agent_list = [
            {"id": "vision", "name": "Vision / OCR Agent", "role": "Document Forensics"},
            {"id": "finance", "name": "Finance Agent", "role": "Transaction Audit"},
            {"id": "stylometric", "name": "Stylometric Agent", "role": "Writing Fingerprint"},
            {"id": "voice", "name": "Voice Authenticity Agent", "role": "Acoustic Forensics"},
            {"id": "threat_intel", "name": "Threat Intel Agent", "role": "Domain / IP Reputation"},
            {"id": "nlp", "name": "NLP Agent", "role": "Scam Classification"},
            {"id": "policy", "name": "Policy Agent", "role": "Authority & Approval Check"},
            {"id": "compliance", "name": "Compliance Agent", "role": "Regulatory RAG"},
        ]
        await _emit(q, "agents_started", {"agents": agent_list})

        # ── 4. Run all agents concurrently ────────────────────────────────────
        # Download the supplied evidence file so Vision analyzes the REAL
        # document. Fails soft to None (Vision then behaves as before).
        evidence_path = await download_evidence(file_url) if file_url else None
        if evidence_path:
            await _emit(q, "evidence_ingested", {"analyzing_real_file": True})
            # File forensics pre-pass (#5) — runs BEFORE any agent touches the
            # file: entropy scan + data hidden after the EOF marker.
            try:
                from sentinel.file_forensics import scan as forensics_scan

                fx = forensics_scan(evidence_path)
                await _emit(q, "file_forensics", {
                    "suspicious": fx.suspicious,
                    "summary": fx.summary,
                    "hidden_payloads": [p.preview for p in fx.hidden_payloads],
                    "entropy_anomalies": len(fx.entropy_anomalies),
                    "source_pointers": fx.source_pointers[:5],
                })
                if fx.suspicious:
                    await repo.append_audit_event(
                        case_id=case_id,
                        event_type="file_forensics",
                        payload={"summary": fx.summary,
                                 "hidden": [p.preview for p in fx.hidden_payloads]},
                    )
            except Exception as e:
                log.warning("file forensics failed: %s", e)

        # Scan the real domain from the report text (fixes the hardcoded stub).
        _dm = _DOMAIN_RE.search(event_text or "")
        domain_to_scan = _dm.group(1) if _dm else "example.com"

        # MCP baseline retrieval — pull the sender's prior writing so the
        # stylometric agent has a real fingerprint to compare against. This is
        # the MCP required-tech story; falls back to a curated seed with no token.
        from sentinel.mcp_baseline import fetch_writing_baseline
        baseline_samples = await fetch_writing_baseline(reporter, channel=channel)
        if baseline_samples:
            await _emit(q, "mcp_baseline", {
                "user": reporter,
                "sample_count": len(baseline_samples),
                "source": "slack_search" if len(baseline_samples) > 3 else "curated",
            })

        agent_tasks = {
            "vision": asyncio.to_thread(vision_agent.analyze, case_id, evidence_path),
            "finance": asyncio.to_thread(finance_agent.analyze, case_id),
            "stylometric": asyncio.to_thread(
                stylometric_agent.analyze, case_id, reporter, event_text,
                baseline_samples=baseline_samples or None,
            ),
            "voice": asyncio.to_thread(voice_agent.analyze, case_id, reporter),
            "threat_intel": asyncio.to_thread(
                threat_intel_agent.analyze, case_id, domain_to_scan
            ),
            "nlp": asyncio.to_thread(nlp_agent.analyze, case_id, event_text),
            "policy": asyncio.to_thread(
                policy_agent.analyze, case_id, amount_at_risk or 1450000.0, [reporter]
            ),
            "compliance": asyncio.to_thread(
                compliance_analyze, case_id, event_text
            ),
        }

        claims: list[Claim] = []
        compliance_result = None

        # Run agents with individual completion events
        results_map: dict[str, Any] = {}
        t_start = time.perf_counter()

        # Map each future to its agent name for O(1) lookup on completion
        # (avoids an O(n) identity scan per finished future, and the
        # StopIteration risk if the scan ever fails to match).
        future_to_name = {
            asyncio.ensure_future(coro): name for name, coro in agent_tasks.items()
        }
        pending = set(future_to_name)

        while pending:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            for fut in done:
                agent_name = future_to_name[fut]
                elapsed = round((time.perf_counter() - t_start) * 1000, 1)

                try:
                    result = fut.result()
                    results_map[agent_name] = result

                    # Extract claims
                    agent_claims: list[Claim] = []
                    if agent_name == "compliance":
                        compliance_result = result
                        claims_payload = {
                            "should_file_sar": result.should_file_sar,
                            "answer": result.answer[:150],
                        }
                    else:
                        # harvest_claims handles BOTH to_claims() (plural) and
                        # to_claim() (singular). Voice/Stylometric/Policy use the
                        # singular form and were previously dropped here.
                        agent_claims = harvest_claims(result)
                        claims.extend(agent_claims)
                        claims_payload = {
                            "claim_count": len(agent_claims),
                            "fields": [c.field for c in agent_claims],
                        }

                    await _emit(q, "agent_complete", {
                        "agent_id": agent_name,
                        "agent_name": next(
                            a["name"] for a in agent_list if a["id"] == agent_name
                        ),
                        "status": "complete",
                        "elapsed_ms": elapsed,
                        "claims": claims_payload,
                    })

                except Exception as e:
                    log.error("Agent %s failed: %s", agent_name, e)
                    await _emit(q, "agent_complete", {
                        "agent_id": agent_name,
                        "agent_name": agent_name,
                        "status": "error",
                        "elapsed_ms": elapsed,
                        "error": str(e)[:120],
                        "claims": {},
                    })

        # ── 4a. Curated demo signals ─────────────────────────────────────────
        # For the flagship demo, inject the curated cross-modal evidence the
        # live agents cannot produce without a real audio clip + writing
        # baseline. Appended last so they win the field key in the reconciler.
        # Honestly labelled as curated (Master Reference §13).
        if demo_case:
            from sentinel.demo_fixtures import demo_claims

            # Drop the placeholder voice claim and replace it with a REAL run of
            # the acoustic detector on a curated cloned clip (measured score+AUC).
            curated = [c for c in demo_claims(case_id) if c.field != "voice_mismatch"]
            vres = voice_agent.demo_voice_result(case_id, reporter)
            curated.append(vres.to_claim())
            claims.extend(curated)
            await _emit(q, "voice_analysis", {
                "spoof_score": vres.spoof_score,
                "voice_mismatch": vres.voice_mismatch,
                "detector_auc": vres.detector_auc,
                "detail": vres.detail,
            })
            await _emit(q, "demo_signals_injected", {
                "curated": True,
                "fields": [c.field for c in curated],
                "note": "Curated demo evidence (real-clip-vs-cloned-clip pair) — "
                        "flows through the same deterministic reconciler.",
            })

        # ── 4b. Temporal recall — with the real agent claims (#21) ────────────
        claims_dict = {c.field: c.value for c in claims}
        prior_cases = await temporal_recall(
            case_id=case_id,
            claims_dict=claims_dict,
            verdict="PENDING",
            channel=channel,
            rts_query=event_text,
        )
        recall_payload = []
        if prior_cases:
            recall_payload = [
                {
                    "case_id": p.case_id[:8],
                    "similarity": round(p.similarity, 2),
                    "verdict": p.verdict,
                    "found_via": p.found_via,
                }
                for p in prior_cases[:3]
            ]
        await _emit(q, "temporal_recall", {"similar_cases": recall_payload})

        # ── 5. Confidence-Calibrated Silence (#18) ────────────────────────────
        should_silence, silence_reason = _check_silence(claims)
        if should_silence:
            await _emit(q, "silence_triggered", {
                "reason": silence_reason,
                "verdict": "NEED_MORE_INFO",
                "risk": 0.0,
                "missing": _missing_modalities(claims),
            })
            try:
                await repo.update_case_status(
                    case_id, status="verdict", risk_score=0.0, verdict="NEED_MORE_INFO"
                )
            except Exception as e:
                # Requires migration 002 for the NEED_MORE_INFO CHECK value.
                # Never let a persistence hiccup abort the stream.
                log.warning("Could not persist NEED_MORE_INFO verdict: %s", e)
            await _emit(q, "stream_end", {"case_id": case_id})
            return

        # ── 6. Contradiction engine (#15) ─────────────────────────────────────
        # Load any analyst-promoted 'enforced' rules first; a match short-
        # circuits the full engine (ticket #26 — "a later case trips the rule").
        enforced_rules = []
        try:
            stored = await repo.list_rules(status="enforced")
            enforced_rules = [Rule.from_dict(r.rule_json) for r in stored]
        except Exception as e:
            log.warning("Could not load enforced rules: %s", e)

        verdict_obj = run_case(claims=claims, enforced_rules=enforced_rules)
        contradiction_axes = [c.axis for c in verdict_obj.contradictions]

        await _emit(q, "contradiction_result", {
            "verdict": verdict_obj.verdict,
            "risk": verdict_obj.risk,
            "contradictions": [
                {
                    "axis": c.axis,
                    "detail": c.detail,
                    "weight": c.weight,
                    "evidence": c.evidence,
                }
                for c in verdict_obj.contradictions
            ],
            "counterfactual": verdict_obj.counterfactual,
        })

        # ── 7. Blast radius (#19, #20) ────────────────────────────────────────
        blast_data: dict = {"nodes": [], "edges": [], "summary": ""}
        if verdict_obj.verdict in ("FRAUD_LIKELY", "REVIEW"):
            try:
                from sentinel.graph.blast_radius import blast_radius
                br_result = await blast_radius(reporter, depth=3)
                blast_data = {
                    "nodes": br_result.nodes,
                    "edges": br_result.edges,
                    "summary": br_result.summary,
                    "total_reached": br_result.total_reached,
                    "super_spreader": br_result.super_spreader,
                    "campaign_cluster_count": br_result.campaign_cluster_count,
                }
                # Seed demo graph nodes if empty (for the demo path)
                if not br_result.nodes:
                    blast_data["nodes"] = _demo_blast_nodes(reporter)
                    blast_data["edges"] = _demo_blast_edges(reporter)
                    blast_data["summary"] = (
                        f"Pattern touched 3 channel(s) in 14 days. "
                        f"Propagation hub: {reporter} [demo graph]"
                    )
            except Exception as e:
                log.warning("Blast radius failed: %s", e)
                blast_data = {
                    "nodes": _demo_blast_nodes(reporter),
                    "edges": _demo_blast_edges(reporter),
                    "summary": "Demo blast-radius graph (live graph building...)",
                }

        await _emit(q, "blast_radius", blast_data)

        # ── 8. Rule synthesis (#26) ───────────────────────────────────────────
        synthesized_rule = None
        if verdict_obj.verdict == "FRAUD_LIKELY":
            try:
                synthesized_rule = synthesize_rule(case_id, verdict_obj, claims)
                if synthesized_rule:
                    await repo.save_rule(synthesized_rule)
                    await _emit(q, "rule_synthesized", {
                        "rule_id": synthesized_rule.rule_id,
                        "description": synthesized_rule.description,
                        "status": synthesized_rule.status,
                        "conditions": (
                            synthesized_rule.conditions
                            if isinstance(synthesized_rule.conditions, dict)
                            else {}
                        ),
                    })
                    await repo.append_audit_event(
                        case_id=case_id,
                        event_type="rule_synthesized",
                        payload={
                            "rule_id": synthesized_rule.rule_id,
                            "description": synthesized_rule.description,
                        },
                    )
            except Exception as e:
                log.warning("Rule synthesis failed: %s", e)

        # ── 9. Federated pattern check (#29 — SIMULATED) ─────────────────────
        has_voice = any(c.field == "voice_mismatch" for c in claims)
        has_injection = any(c.field == "injection_present" for c in claims)
        has_young_domain = any(
            c.field == "domain_age_days" and isinstance(c.value, (int, float)) and c.value < 30
            for c in claims
        )
        fed_result = check_federation(
            case_id=case_id,
            contradiction_axes=contradiction_axes,
            domain_age_flag=has_young_domain,
            has_voice=has_voice,
            has_injection=has_injection,
        )
        await _emit(q, "federation_check", fed_result.to_dict())

        # ── 10. Compliance check (#13) ────────────────────────────────────────
        if compliance_result:
            await _emit(q, "compliance_check", compliance_result.to_dict())

        # ── 11. Red-Team sub-agent (#16) ──────────────────────────────────────
        red_team = None
        if verdict_obj.verdict in ("FRAUD_LIKELY", "REVIEW"):
            try:
                red_team = generate_defense(claims, verdict=verdict_obj.verdict)
                await _emit(q, "red_team", {
                    "defense": red_team.get("defense", ""),
                    "track_record": red_team.get("track_record", ""),
                })

                # Adversarial self-play (#17): Sentinel forges the strongest fake
                # of this document type and checks whether its own engine catches it.
                try:
                    doc_type = "voice_note" if any(
                        c.field == "voice_mismatch" for c in claims
                    ) else "invoice"
                    sp = run_self_play(doc_type)
                    await _emit(q, "self_play", sp)
                except Exception as e:
                    log.warning("self-play failed: %s", e)
            except Exception as e:
                log.warning("Red team failed: %s", e)

        # ── 12. Honeypot (#25 — FRAUD_LIKELY only, SIMULATED) ─────────────────
        if verdict_obj.verdict == "FRAUD_LIKELY":
            try:
                hp = run_honeypot(case_id, turns=3)
                await _emit(q, "honeypot_result", hp.to_dict())
            except Exception as e:
                log.warning("Honeypot failed: %s", e)

        # ── 13. Expected-loss triage (#24) ────────────────────────────────────
        if amount_at_risk > 0:
            loss_data = _compute_expected_loss(verdict_obj.risk, amount_at_risk)
            await _emit(q, "expected_loss", loss_data)

        # ── 14. Persist verdict ───────────────────────────────────────────────
        from dataclasses import asdict as _asdict
        await repo.save_agent_results(
            case_id=case_id,
            agent_name="contradiction_engine",
            claims=[],
            contradictions=[_asdict(c) for c in verdict_obj.contradictions],
        )
        await repo.update_case_status(
            case_id,
            status="verdict",
            risk_score=verdict_obj.risk,
            verdict=verdict_obj.verdict,
        )
        await repo.append_audit_event(
            case_id=case_id,
            event_type="verdict",
            payload={
                "verdict": verdict_obj.verdict,
                "risk": verdict_obj.risk,
                "contradiction_count": len(verdict_obj.contradictions),
            },
        )

        # Register for active-learning (#28)
        register_case_score(case_id, verdict_obj.risk, verdict_obj.verdict)

        # ── 15. Emit final verdict ────────────────────────────────────────────
        await _emit(q, "verdict", {
            "case_id": case_id,
            "short_id": short_id,
            "verdict": verdict_obj.verdict,
            "risk": verdict_obj.risk,
            "contradictions": [
                {"axis": c.axis, "detail": c.detail, "weight": c.weight}
                for c in verdict_obj.contradictions
            ],
            "counterfactual": verdict_obj.counterfactual,
            "red_team_defense": red_team,
            "rule_id": synthesized_rule.rule_id if synthesized_rule else None,
        })

    except Exception as e:
        log.exception("SSE worker fatal error for case %s: %s", case_id[:8], e)
        await _emit(q, "error", {"message": str(e), "case_id": case_id})

    finally:
        cleanup_evidence(evidence_path)
        await _emit(q, "stream_end", {"case_id": case_id})
        # Give the consumer a moment to drain, then cleanup
        await asyncio.sleep(2)
        cleanup_case_queue(case_id)
        log.info("SSE worker done for case %s", case_id[:8])


# ── Demo graph nodes (for the standalone React console path) ───────────────────

def _demo_blast_nodes(reporter: str) -> list[dict]:
    """Return demo blast-radius nodes for when the graph cache is empty."""
    return [
        {"id": reporter, "node_type": "user", "label": "Reporter", "is_origin": True},
        {"id": "C_GENERAL", "node_type": "channel", "label": "#general", "is_origin": False},
        {"id": "C_FINANCE", "node_type": "channel", "label": "#finance", "is_origin": False},
        {"id": "C_PAYMENTS", "node_type": "channel", "label": "#payments", "is_origin": False},
        {"id": "U_CFO", "node_type": "user", "label": "CFO_Account", "is_origin": False},
        {"id": "U_ACCOUNTANT", "node_type": "user", "label": "Accountant_1", "is_origin": False},
        {"id": "F_INVOICE", "node_type": "file", "label": "invoice_9108A.pdf", "is_origin": False},
    ]


def _demo_blast_edges(reporter: str) -> list[dict]:
    return [
        {"source": reporter, "target": "C_GENERAL", "edge_type": "message", "count": 3},
        {"source": reporter, "target": "C_FINANCE", "edge_type": "message", "count": 7},
        {"source": "C_FINANCE", "target": "U_CFO", "edge_type": "mention", "count": 2},
        {"source": "C_FINANCE", "target": "U_ACCOUNTANT", "edge_type": "mention", "count": 4},
        {"source": "U_ACCOUNTANT", "target": "C_PAYMENTS", "edge_type": "message", "count": 5},
        {"source": "C_PAYMENTS", "target": "F_INVOICE", "edge_type": "file_share", "count": 1},
    ]
