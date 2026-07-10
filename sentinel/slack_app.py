"""Slack Bolt app instance (build-map ticket #1).

The Bolt AsyncApp is created here once and imported by:
  - gateway.py   → mounts it on FastAPI's ASGI stack
  - worker.py    → uses `app.client` to post Block Kit cards back to Slack

Rule: NOTHING that takes > ~5ms happens inside a Bolt handler.
      Handlers only (1) ACK and (2) hand off to BackgroundTasks.
      The out-of-band worker (worker.py) does all real work.

Event subscriptions required in api.slack.com → Event Subscriptions:
  app_mention
  message.channels
  message.groups
  file_shared
  member_joined_channel
"""

from __future__ import annotations

import logging
import os

from slack_bolt.async_app import AsyncApp  # type: ignore

from sentinel.graph.slack_events import register_graph_listeners

log = logging.getLogger(__name__)

# ── App instance ──────────────────────────────────────────────────────────────
# Bolt refuses to construct without a token. When Slack credentials are not
# configured (e.g. the React-console / API-only path, CI, or a bare Docker
# boot), fall back to inert placeholders and skip the startup auth.test so the
# gateway still serves its REST/SSE endpoints. Real credentials take over
# automatically whenever the env vars are set.
_slack_token = os.environ.get("SLACK_BOT_TOKEN") or "xoxb-not-configured"
_slack_secret = os.environ.get("SLACK_SIGNING_SECRET") or "not-configured"
_slack_configured = bool(os.environ.get("SLACK_BOT_TOKEN"))
if not _slack_configured:
    log.warning(
        "SLACK_BOT_TOKEN not set — Slack app running in inert mode "
        "(REST/SSE endpoints work; live Slack events will not)."
    )

app = AsyncApp(
    token=_slack_token,
    signing_secret=_slack_secret,
)

# Register the graph-ingestion listeners (ticket #3)
register_graph_listeners(app)


# ── @Sentinel investigate handler ─────────────────────────────────────────────
# NOTE: This is intentionally a thin stub — the real work is injected by
# gateway.py via FastAPI BackgroundTasks after the ACK returns.
# The handler here only posts the "Case created…" acknowledgement card.


@app.event("app_mention")
async def on_mention(event: dict, say, ack) -> None:
    """ACK Slack immediately; gateway.py will enqueue the background worker."""
    await ack()
    # The case number will be filled in by the worker once persisted;
    # we post a placeholder "investigating…" card right away.
    channel = event.get("channel", "")
    ts = event.get("ts", "")
    await say(
        channel=channel,
        thread_ts=ts,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        ":rotating_light: *Sentinel* — investigating…\n"
                        "_Specialist agents spinning up. I'll update this thread as results arrive._"
                    ),
                },
            }
        ],
        text="Sentinel is investigating…",
    )
    log.info("app_mention ACKed for channel=%s ts=%s", channel, ts)


# ── App Home SOC dashboard (ticket #31) ────────────────────────────────────────


@app.event("app_home_opened")
async def on_home_opened(event: dict, client) -> None:
    """Publish the SOC dashboard when a user opens the App Home tab."""
    from sentinel.db import repo
    from sentinel.slack_ui import home_view

    user = event.get("user", "")
    try:
        cases = await repo.list_cases(limit=25)
    except Exception as e:
        log.warning("home tab: could not load cases: %s", e)
        cases = []
    try:
        await client.views_publish(user_id=user, view=home_view(cases))
    except Exception as e:
        log.warning("home tab: views_publish failed: %s", e)


# ── Verdict card action buttons ────────────────────────────────────────────────


@app.action("promote_rule")
async def on_promote_rule(ack, body, client) -> None:
    """Promote a shadow rule to enforced from the Slack button (ticket #26)."""
    await ack()
    from sentinel.db import repo

    rule_id = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    ts = body["message"]["ts"]
    try:
        await repo.promote_rule(rule_id)
        await repo.append_audit_event(
            case_id="system",
            event_type="rule_promoted",
            payload={"rule_id": rule_id, "via": "slack", "by": body["user"]["id"]},
        )
        await client.chat_postMessage(
            channel=channel,
            thread_ts=ts,
            text=f":white_check_mark: Rule `{rule_id[:8]}` promoted to *enforced*. "
            "Future matching cases resolve instantly.",
        )
    except Exception as e:
        log.warning("promote_rule action failed: %s", e)
        await client.chat_postMessage(
            channel=channel, thread_ts=ts, text=":warning: Could not promote rule."
        )


@app.action("quarantine_case")
async def on_quarantine(ack, body, client) -> None:
    """Quarantine the blast-radius nodes for a case (ticket #22)."""
    await ack()
    case_id = body["actions"][0]["value"]
    user = body["user"]["id"]
    channel = body["channel"]["id"]
    ts = body["message"]["ts"]
    try:
        from sentinel.graph.blast_radius import blast_radius
        from sentinel.graph.quarantine import quarantine

        br = await blast_radius(user, depth=2)
        node_ids = [n["id"] for n in getattr(br, "nodes", [])][:20] or [user]
        quarantine(
            case_id=case_id,
            node_ids=node_ids,
            reason="Analyst quarantine via Slack verdict card",
            quarantined_by=user,
        )
        await client.chat_postMessage(
            channel=channel,
            thread_ts=ts,
            text=f":lock: Quarantined {len(node_ids)} node(s) for case "
            f"`{case_id[:8]}`. Audit entry written.",
        )
    except Exception as e:
        log.warning("quarantine action failed: %s", e)
        await client.chat_postMessage(
            channel=channel, thread_ts=ts, text=":warning: Quarantine failed."
        )
