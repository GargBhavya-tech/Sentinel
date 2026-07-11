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
import os
import re
from typing import Any

import asyncio
from sentinel.db import repo
from sentinel.ingest import download_evidence, cleanup_evidence, first_supported_file
from sentinel.pipeline import run_case
from sentinel.rules.schema import Rule
from sentinel.slack_app import app
from sentinel.agents import (
    vision_agent,
    finance_agent,
    stylometric_agent,
    voice_agent,
    threat_intel_agent,
    nlp_agent,
    policy_agent,
)
from sentinel.claims import Claim
from sentinel.agents.harvest import harvest_claims
from sentinel.rules.synthesizer import synthesize_rule
from sentinel.recall import recall as temporal_recall
from sentinel.slack_ui import verdict_action_blocks, create_case_canvas

log = logging.getLogger(__name__)

# First bare domain in free text (e.g. "wire to acme-payments.com"). Used to
# feed the threat-intel agent a real domain instead of a hardcoded stub.
_DOMAIN_RE = re.compile(
    r"\b([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.(?:[a-z]{2,}))\b", re.IGNORECASE
)


def _extract_domain(text: str) -> str | None:
    m = _DOMAIN_RE.search(text or "")
    return m.group(1) if m else None


# ── Block Kit card builders ────────────────────────────────────────────────────


def _verdict_emoji(verdict: str) -> str:
    return {
        "FRAUD_LIKELY": ":red_circle:",
        "REVIEW": ":large_yellow_circle:",
        "CLEAR": ":large_green_circle:",
        "NEED_MORE_INFO": ":question:",
    }.get(verdict, ":white_circle:")


def _build_verdict_card(
    case_id: str,
    verdict_obj,
    red_team_defense: dict | None = None,
    rule_id: str | None = None,
) -> list[dict]:
    """Assemble the Phase 0/2 verdict Block Kit card.

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

    if verdict_obj.verdict == "NEED_MORE_INFO":
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{verdict_obj.counterfactual}*"},
            }
        )
        blocks.append({"type": "divider"})
        return blocks

    if verdict_obj.contradictions:
        lines = []
        for c in verdict_obj.contradictions:
            lines.append(f"• *{c.axis}* — {c.detail}")
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Contradiction axes fired:*\n" + "\n".join(lines),
                },
            }
        )

    if verdict_obj.counterfactual:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":bulb: *Counterfactual:* {verdict_obj.counterfactual}",
                    }
                ],
            }
        )

    if red_team_defense:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":shield: *Red Team Defense:*\n_{red_team_defense['defense']}_\n*(Track Record: {red_team_defense['track_record']})*",
                },
            }
        )

    # Action buttons for the analyst (Quarantine #22 / Promote Rule #26).
    if verdict_obj.verdict in ("FRAUD_LIKELY", "REVIEW"):
        blocks.append(verdict_action_blocks(case_id, rule_id))

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

    # Announce the created case as a thread reply.
    #
    # We POST a new message rather than chat_update the mention's ts: a bot
    # cannot edit the user's mention message, and the "investigating…"
    # placeholder posted by slack_app.on_mention lives under a ts that isn't
    # available in this out-of-band worker. Temporal recall (#21) runs later,
    # once the real agent claims exist — an empty claims_dict embeds to the
    # zero vector and can never match anything.
    short_id = case.case_id[:8]
    await app.client.chat_postMessage(
        channel=channel,
        thread_ts=ts,
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
    # Feed the agents the real event signal (reporter + message text) rather
    # than hardcoded stubs, so the verdict reflects the actual report.
    event_text = event.get("text", "") or ""
    stylo_text = event_text or "(no message text)"
    domain = _extract_domain(event_text)

    # Download the first attached file so Vision analyzes the REAL document
    # (not a placeholder). Fails soft to None → same behaviour as before.
    evidence_path = None
    picked = first_supported_file(event.get("files", []))
    if picked:
        evidence_path = await download_evidence(
            picked.get("url_private", ""),
            slack_token=os.environ.get("SLACK_BOT_TOKEN"),
            filename=picked.get("name"),
        )
        if evidence_path:
            log.info("Vision analyzing real evidence: %s", picked.get("name"))
            # File forensics pre-pass (#5) — entropy + post-EOF hidden payloads.
            try:
                from sentinel.file_forensics import scan as forensics_scan

                fx = forensics_scan(evidence_path)
                if fx.suspicious:
                    payloads = "; ".join(p.preview for p in fx.hidden_payloads) or fx.summary
                    await app.client.chat_postMessage(
                        channel=channel,
                        thread_ts=ts,
                        text=(
                            f":microscope: *File forensics* flagged "
                            f"`{picked.get('name')}` — {fx.summary}. "
                            f"Hidden content: `{payloads[:200]}`"
                        ),
                    )
                    await repo.append_audit_event(
                        case_id=case.case_id,
                        event_type="file_forensics",
                        payload={"summary": fx.summary},
                    )
            except Exception as e:
                log.warning("file forensics failed: %s", e)

    # MCP baseline retrieval — the sender's prior writing, so the stylometric
    # agent has a real fingerprint to compare against (MCP required-tech story).
    from sentinel.mcp_baseline import fetch_writing_baseline

    baseline_samples = await fetch_writing_baseline(reporter, channel=channel)

    # Run all agents concurrently using asyncio.to_thread
    agent_tasks = [
        asyncio.to_thread(vision_agent.analyze, case.case_id, evidence_path),
        asyncio.to_thread(finance_agent.analyze, case.case_id),
        asyncio.to_thread(
            stylometric_agent.analyze, case.case_id, reporter, stylo_text,
            baseline_samples=baseline_samples or None,
        ),
        asyncio.to_thread(voice_agent.analyze, case.case_id, reporter),
        asyncio.to_thread(nlp_agent.analyze, case.case_id, stylo_text),
        asyncio.to_thread(policy_agent.analyze, case.case_id, 0.0, [reporter]),
    ]
    # Only run threat-intel when the report actually references a domain.
    if domain:
        agent_tasks.append(
            asyncio.to_thread(threat_intel_agent.analyze, case.case_id, domain)
        )

    results = await asyncio.gather(*agent_tasks, return_exceptions=True)
    claims: list[Claim] = []

    for res in results:
        if isinstance(res, Exception):
            log.error("Agent failed: %s", res)
            continue
        # harvest_claims handles BOTH to_claims() (plural) and to_claim()
        # (singular) — the latter is what Voice/Stylometric/Policy expose, and
        # was previously dropped, disabling the voice + tone contradiction axes.
        claims.extend(harvest_claims(res))

    # If the event contains file attachments, store them as evidence stubs.
    for f in event.get("files", []):
        await repo.insert_evidence(
            case_id=case.case_id,
            evidence_type="file",
            file_url=f.get("url_private", ""),
            raw_metrics={},
        )
        log.info("Evidence stored: %s", f.get("name"))

    # ── 3b. Temporal Recall — now that real agent claims exist (ticket #21) ───
    claims_dict = {c.field: c.value for c in claims}
    prior_cases = await temporal_recall(
        case_id=case.case_id,
        claims_dict=claims_dict,
        verdict="PENDING",
        channel=channel,
        rts_query=event_text or "invoice fraud",
    )
    if prior_cases:
        best = prior_cases[0]
        prior_blurb = (
            f":mag: *Prior similar case found* — "
            f"`{best.case_id[:8]}` (similarity {best.similarity:.0%}, "
            f"verdict `{best.verdict}`) [{best.found_via}]"
        )
        await app.client.chat_postMessage(
            channel=channel,
            thread_ts=ts,
            text=prior_blurb,
            blocks=[{
                "type": "section",
                "text": {"type": "mrkdwn", "text": prior_blurb},
            }],
        )
        log.info(
            "Temporal recall: %d prior case(s) found for %s",
            len(prior_cases), case.case_id,
        )

    # ── 3c. Load enforced self-writing rules (ticket #26) ─────────────────────
    # An earlier case may have synthesized a rule that an analyst promoted to
    # 'enforced'. If it fires, run_case short-circuits the full engine.
    enforced_rules: list[Rule] = []
    try:
        stored = await repo.list_rules(status="enforced")
        enforced_rules = [Rule.from_dict(r.rule_json) for r in stored]
    except Exception as e:
        log.warning("Could not load enforced rules: %s", e)

    # ── 4. Run contradiction engine ───────────────────────────────────────────
    verdict_obj = run_case(claims=claims, enforced_rules=enforced_rules)
    log.info(
        "Case %s verdict: %s (risk=%.3f)",
        case.case_id,
        verdict_obj.verdict,
        verdict_obj.risk,
    )

    # ── 4a. Self-Writing Rule Synthesis (ticket #26) ──────────────────────
    synthesized_rule = None
    if verdict_obj.verdict == "FRAUD_LIKELY":
        synthesized_rule = synthesize_rule(case.case_id, verdict_obj, claims)
        if synthesized_rule:
            # Persist to DB (shadow status)
            try:
                await repo.save_rule(synthesized_rule)
                log.info(
                    "Shadow rule %s synthesized for case %s",
                    synthesized_rule.rule_id[:8],
                    case.case_id,
                )
                await repo.append_audit_event(
                    case_id=case.case_id,
                    event_type="rule_synthesized",
                    payload={
                        "rule_id": synthesized_rule.rule_id,
                        "description": synthesized_rule.description,
                        "status": "shadow",
                    },
                )
            except Exception as e:
                log.warning("Could not persist rule to DB: %s", e)

    # ── 4b. Graph Analytics (Blast Radius) on Confirmed Threat ──────────────
    if verdict_obj.verdict == "FRAUD_LIKELY":
        from sentinel.graph.cache import neighbors
        from sentinel.graph.analytics import analyze_blast_radius

        # Run BFS to find blast radius
        blast_nodes = await neighbors(reporter, depth=2)
        if blast_nodes:
            log.info(
                "Blast radius for %s: %d nodes touched", reporter, len(blast_nodes)
            )
        # Run PageRank and Clusters
        graph_stats = analyze_blast_radius([reporter])
        if graph_stats.get("super_spreader"):
            log.info("Identified super-spreader: %s", graph_stats["super_spreader"])

    # ── 4c. Red-Team Sub-Agent (Phase 3 Support) ─────────────────────────────
    red_team_defense = None
    if verdict_obj.verdict in ("FRAUD_LIKELY", "REVIEW"):
        from sentinel.agents.red_team_agent import generate_defense

        red_team_defense = generate_defense(claims, verdict=verdict_obj.verdict)
        log.info("Red Team defense generated: %s", red_team_defense["defense"])

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
    blocks = _build_verdict_card(
        case.case_id,
        verdict_obj,
        red_team_defense,
        rule_id=synthesized_rule.rule_id if synthesized_rule else None,
    )
    await app.client.chat_postMessage(
        channel=channel,
        thread_ts=ts,
        blocks=blocks,
        text=f"Sentinel verdict for Case #{short_id}: {verdict_obj.verdict}",
    )
    log.info("Case %s verdict card posted to Slack", case.case_id)

    # Ticket #33 — per-case Slack Canvas (fails soft without canvases:write).
    if verdict_obj.verdict in ("FRAUD_LIKELY", "REVIEW"):
        canvas_id = await create_case_canvas(app.client, case.case_id, verdict_obj)
        if canvas_id:
            await app.client.chat_postMessage(
                channel=channel,
                thread_ts=ts,
                text=f":page_facing_up: Case Canvas created for #{short_id}.",
            )

    # Remove the downloaded evidence temp file now the agents are done.
    cleanup_evidence(evidence_path)
