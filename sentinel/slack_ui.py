"""Slack surfaces — Block Kit builders, App Home view, and Canvas helpers.

Centralizes everything that renders into Slack so worker.py and slack_app.py
stay focused on flow. Three surfaces live here:

  1. verdict_action_blocks() — the action buttons on a verdict card
     (Quarantine → ticket #22, Promote Rule → ticket #26).
  2. home_view()            — the App Home SOC dashboard with an ambient
     "all clear" resting state (part of ticket #31).
  3. create_case_canvas()   — a per-case Slack Canvas file (ticket #33).

Canvas requires the `canvases:write` scope; if it's missing the helper logs a
warning and returns None rather than failing the investigation.
"""

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


# ── 1. Verdict card action buttons (#22 quarantine, #26 promote) ───────────────

def verdict_action_blocks(case_id: str, rule_id: Optional[str] = None) -> dict:
    """An `actions` block with Quarantine (+ Promote Rule when a rule exists)."""
    elements = [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": ":lock: Quarantine", "emoji": True},
            "style": "danger",
            "action_id": "quarantine_case",
            "value": case_id,
            "confirm": {
                "title": {"type": "plain_text", "text": "Quarantine payload?"},
                "text": {
                    "type": "mrkdwn",
                    "text": "This redacts the flagged content from the localized "
                    "instances found by the blast-radius mapper and writes an "
                    "audit entry.",
                },
                "confirm": {"type": "plain_text", "text": "Quarantine"},
                "deny": {"type": "plain_text", "text": "Cancel"},
            },
        }
    ]
    if rule_id:
        elements.append(
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":white_check_mark: Promote Rule",
                    "emoji": True,
                },
                "style": "primary",
                "action_id": "promote_rule",
                "value": rule_id,
            }
        )
    return {"type": "actions", "block_id": f"verdict_actions::{case_id}", "elements": elements}


# ── 2. App Home SOC dashboard (#31) ────────────────────────────────────────────

_VERDICT_GLYPH = {
    "FRAUD_LIKELY": ":red_circle:",
    "REVIEW": ":large_yellow_circle:",
    "CLEAR": ":large_green_circle:",
    "NEED_MORE_INFO": ":question:",
}


def home_view(cases: list) -> dict:
    """Build the App Home `home` view from a list of Case dataclasses.

    Shows an ambient "all clear" state when nothing needs attention, otherwise a
    triage list of the most recent active (FRAUD_LIKELY / REVIEW) cases.
    """
    active = [
        c for c in cases if getattr(c, "verdict", None) in ("FRAUD_LIKELY", "REVIEW")
    ]

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🛡️  Sentinel — SOC Dashboard", "emoji": True},
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"Monitoring *{len(cases)}* case(s) · "
                        f"*{len(active)}* need attention"
                    ),
                }
            ],
        },
        {"type": "divider"},
    ]

    if not active:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        ":large_green_circle:  *All clear.*\n"
                        "No active threats. Sentinel is watching the workspace — "
                        "forward a suspicious invoice, CSV, or voice note and type "
                        "`@Sentinel investigate` to open a case."
                    ),
                },
            }
        )
        return {"type": "home", "blocks": blocks}

    for c in active[:10]:
        glyph = _VERDICT_GLYPH.get(getattr(c, "verdict", ""), ":white_circle:")
        risk = getattr(c, "risk_score", None)
        risk_txt = f"{risk * 100:.0f}%" if isinstance(risk, (int, float)) else "—"
        cid = str(getattr(c, "case_id", ""))[:8]
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{glyph}  *Case #{cid}* · `{getattr(c, 'verdict', '?')}` · "
                        f"risk *{risk_txt}*\n"
                        f"_channel_ `{getattr(c, 'slack_channel', '—')}` · "
                        f"_status_ `{getattr(c, 'status', '—')}`"
                    ),
                },
            }
        )

    return {"type": "home", "blocks": blocks}


# ── 3. Slack Canvas case file (#33) ────────────────────────────────────────────

def _case_markdown(case_id: str, verdict_obj) -> str:
    """Render a case as Canvas markdown."""
    lines = [
        f"# Sentinel Case #{case_id[:8]}",
        "",
        f"**Verdict:** `{verdict_obj.verdict}`  ·  **Risk:** {verdict_obj.risk * 100:.0f}%",
        "",
        "## Contradiction axes",
    ]
    if verdict_obj.contradictions:
        for c in verdict_obj.contradictions:
            lines.append(f"- **{c.axis}** — {c.detail}")
    else:
        lines.append("- _None fired._")
    if getattr(verdict_obj, "counterfactual", None):
        lines += ["", "## Counterfactual", verdict_obj.counterfactual]
    lines += ["", "---", "_Generated by Sentinel · deterministic contradiction engine._"]
    return "\n".join(lines)


async def create_case_canvas(client, case_id: str, verdict_obj) -> Optional[str]:
    """Create a standalone Slack Canvas for a case; return its id or None.

    Requires the `canvases:write` bot scope. Fails soft — a missing scope or an
    older Slack SDK must never break an investigation.
    """
    try:
        resp = await client.canvases_create(
            title=f"Sentinel Case #{case_id[:8]}",
            document_content={
                "type": "markdown",
                "markdown": _case_markdown(case_id, verdict_obj),
            },
        )
        canvas_id = resp.get("canvas_id")
        log.info("canvas: created %s for case %s", canvas_id, case_id[:8])
        return canvas_id
    except Exception as e:
        log.warning(
            "canvas: create failed (needs canvases:write scope / newer SDK?): %s", e
        )
        return None
