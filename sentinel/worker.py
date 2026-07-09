"""Out-of-band async worker (build-map ticket #1).

This is where ALL real investigation work happens — safely separated from
the Slack webhook ack path so Slack's 3-second timeout can never be hit.

Flow for a @Sentinel investigate mention
-----------------------------------------
1. gateway.py receives the webhook, ACKs Slack via Bolt (< 5ms), then calls
   BackgroundTasks.add_task(investigate, event=event).
2. investigate() runs here, out-of-band:
   a. Create a DB case row (status=analyzing).
   b. Insert evidence (files attached to the message, if any).
   c. Build a `metrics` dict from the evidence (Phase 0: zeroed-out
      stand-ins — real agents land in Phase 2).
   d. Run run_case() through the contradiction engine.
   e. Persist agent results + verdict.
   f. Update case status to 'verdict'.
   g. Append an audit chain entry.
   h. Post the verdict Block Kit card back to the Slack thread.

In Phase 2, step (c) is replaced by the real specialist agents running in
parallel via asyncio.gather(). The rest of the flow is unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

import asyncio
from sentinel.db import repo
from sentinel.pipeline import run_case
from sentinel.slack_app import app
from sentinel.agents import (
    vision_agent,
    finance_agent,
    stylometric_agent,
    voice_agent,
    threat_intel_agent,
    nlp_agent,
    policy_agent
)
from sentinel.claims import Claim

log = logging.getLogger(__name__)


# ── Block Kit card builders ────────────────────────────────────────────────────

def _verdict_emoji(verdict: str) -> str:
    return {
        "FRAUD_LIKELY": ":red_circle:",
        "REVIEW": ":large_yellow_circle:",
        "CLEAR": ":large_green_circle:",
    }.get(verdict, ":white_circle:")


def _build_verdict_card(case_id: str, verdict_obj) -> list[dict]:
    """Assemble the Phase 0 verdict Block Kit card.

    In Phase 2 this grows to include contradiction axes, voice waveform,
    blast-radius graph, and action buttons. For now it posts the core fields.
    """
    emoji = _verdict_emoji(verdict_obj.verdict)
    short_id = case_id[:8]
    risk_pct = f"{verdict_obj.risk * 100:.0f}%"

    blocks: list[dict] = [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{emoji} *Sentinel Verdict — Case #{short_id}*\n"
                    f"*Risk:* {risk_pct}   *Verdict:* `{verdict_obj.verdict}`"
                ),
            },
        },
    ]

    if verdict_obj.contradictions:
        lines = []
        for c in verdict_obj.contradictions:
            lines.append(f"• *{c.axis}* — {c.detail}")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Contradiction axes fired:*\n" + "\n".join(lines),
            },
        })

    if verdict_obj.counterfactual:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f":bulb: *Counterfactual:* {verdict_obj.counterfactual}",
                }
            ],
        })

    blocks.append({"type": "divider"})
    return blocks


# ── Main worker ────────────────────────────────────────────────────────────────

async def investigate(event: dict[str, Any]) -> None:
    """Run a full Sentinel investigation for one @mention event.

    Called by FastAPI BackgroundTasks — never called from the Bolt handler.
    """
    channel = event.get("channel", "")
    ts = event.get("ts", "")
    reporter = event.get("user", "unknown")

    # ── 1. Create case in DB ──────────────────────────────────────────────────
    case = await repo.create_case(
        slack_channel=channel,
        slack_ts=ts,
        reporter_slack_id=reporter,
    )
    log.info("Case %s created (channel=%s)", case.case_id, channel)

    await repo.append_audit_event(
        case_id=case.case_id,
        event_type="case_created",
        payload={"slack_channel": channel, "slack_ts": ts, "reporter": reporter},
    )

    # Update the placeholder card with the real case ID
    short_id = case.case_id[:8]
    await app.client.chat_update(
        channel=channel,
        ts=ts,                          # update the original "investigating…" message
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":rotating_light: *Sentinel* — Case #{short_id} created\n"
                        "_Specialist agents spinning up…_"
                    ),
                },
            }
        ],
        text=f"Sentinel — Case #{short_id} created",
    )

    # ── 2. Update status → analyzing ─────────────────────────────────────────
    await repo.update_case_status(case.case_id, status="analyzing")

    # ── 3. Build claims (Phase 2 real agents) ─────────────────────────────────
    # Run all agents concurrently using asyncio.to_thread
    agent_tasks = [
        asyncio.to_thread(vision_agent.analyze, case.case_id),
        asyncio.to_thread(finance_agent.analyze, case.case_id),
        asyncio.to_thread(stylometric_agent.analyze, case.case_id),
        asyncio.to_thread(voice_agent.analyze, case.case_id),
        asyncio.to_thread(threat_intel_agent.analyze, case.case_id),
        asyncio.to_thread(nlp_agent.analyze, case.case_id),
        asyncio.to_thread(policy_agent.analyze, case.case_id),
    ]
    
    results = await asyncio.gather(*agent_tasks, return_exceptions=True)
    claims: list[Claim] = []
    
    for res in results:
        if isinstance(res, Exception):
            log.error("Agent failed: %s", res)
        elif hasattr(res, "to_claims"):
            claims.extend(res.to_claims())

    # If the event contains file attachments, store them as evidence stubs.
    for f in event.get("files", []):
        await repo.insert_evidence(
            case_id=case.case_id,
            evidence_type="file",
            file_url=f.get("url_private", ""),
            raw_metrics={},
        )
        log.info("Evidence stored: %s", f.get("name"))

    # ── 4. Run contradiction engine ───────────────────────────────────────────
    verdict_obj = run_case(claims=claims)
    log.info("Case %s verdict: %s (risk=%.3f)", case.case_id, verdict_obj.verdict, verdict_obj.risk)

    # ── 4b. Graph Analytics (Blast Radius) on Confirmed Threat ──────────────
    if verdict_obj.verdict == "FRAUD_LIKELY":
        from sentinel.graph.cache import neighbors
        from sentinel.graph.analytics import analyze_blast_radius
        # Run BFS to find blast radius
        blast_nodes = await neighbors(reporter, depth=2)
        if blast_nodes:
            log.info("Blast radius for %s: %d nodes touched", reporter, len(blast_nodes))
        # Run PageRank and Clusters
        graph_stats = analyze_blast_radius([reporter])
        if graph_stats.get("super_spreader"):
            log.info("Identified super-spreader: %s", graph_stats["super_spreader"])

    # ── 5. Persist agent results ──────────────────────────────────────────────
    # Serialize Claim / Contradiction dataclasses to plain dicts for JSONB
    from dataclasses import asdict as _asdict
    await repo.save_agent_results(
        case_id=case.case_id,
        agent_name="contradiction_engine",
        claims=[],
        contradictions=[_asdict(c) for c in verdict_obj.contradictions],
    )

    # ── 6. Update case → verdict ──────────────────────────────────────────────
    await repo.update_case_status(
        case.case_id,
        status="verdict",
        risk_score=verdict_obj.risk,
        verdict=verdict_obj.verdict,
    )

    await repo.append_audit_event(
        case_id=case.case_id,
        event_type="verdict",
        payload={
            "verdict": verdict_obj.verdict,
            "risk": verdict_obj.risk,
            "contradiction_count": len(verdict_obj.contradictions),
        },
    )

    # ── 7. Post verdict card to Slack ─────────────────────────────────────────
    blocks = _build_verdict_card(case.case_id, verdict_obj)
    await app.client.chat_postMessage(
        channel=channel,
        thread_ts=ts,
        blocks=blocks,
        text=f"Sentinel verdict for Case #{short_id}: {verdict_obj.verdict}",
    )
    log.info("Case %s verdict card posted to Slack", case.case_id)
