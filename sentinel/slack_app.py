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
app = AsyncApp(
    token=os.environ.get("SLACK_BOT_TOKEN", ""),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET", ""),
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
