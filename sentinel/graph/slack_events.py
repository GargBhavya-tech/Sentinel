"""Slack event listeners that feed the local graph cache (ticket #3).

These are registered on the Bolt `app` in `slack_app.py` via:

    from sentinel.graph.slack_events import register_graph_listeners
    register_graph_listeners(app)

Every Slack `message` and `file_shared` event that Sentinel's app receives
is piped into the graph cache within milliseconds of the Slack webhook
firing. The BFS blast-radius check (#19) then runs locally in < 1 ms
against that cache instead of hammering the RTS API on every query.
"""

from __future__ import annotations

import logging

from slack_bolt.async_app import AsyncApp  # type: ignore

from .cache import ingest_event

log = logging.getLogger(__name__)


def register_graph_listeners(app: AsyncApp) -> None:
    """Attach all graph-ingestion event handlers to a Bolt app instance."""

    @app.event("message")
    async def on_message(event: dict, ack) -> None:
        await ack()
        # Subtype "message_deleted" / "message_changed" don't add nodes
        if event.get("subtype") in ("message_deleted", "bot_message", "message_replied"):
            return
        await ingest_event(event)
        log.debug("graph: ingested message event ts=%s", event.get("ts"))

    @app.event("file_shared")
    async def on_file_shared(event: dict, ack) -> None:
        await ack()
        await ingest_event(event)
        log.debug("graph: ingested file_shared event file_id=%s", event.get("file_id"))

    @app.event("member_joined_channel")
    async def on_member_joined(event: dict, ack) -> None:
        await ack()
        await ingest_event(event)
        log.debug("graph: ingested member_joined_channel user=%s", event.get("user"))
