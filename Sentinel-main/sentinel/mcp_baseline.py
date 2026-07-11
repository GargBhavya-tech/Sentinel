"""MCP baseline retrieval (build-map ticket #11 / MCP required-tech story).

The Stylometric Agent can only produce a real `tone_anomaly` signal when it has
a *baseline* of the sender's prior writing to compare against. That baseline is
exactly the kind of workspace context MCP exists to retrieve: per-user message
history pulled securely from Slack.

This module is the MCP client seam:

  * When SLACK_BOT_TOKEN is set, `fetch_writing_baseline` retrieves the user's
    recent messages via Slack's search API (the same MCP-style history
    retrieval the Master Reference calls for) and returns them as text samples.
  * When no token is configured (CI, the zero-key demo, the React console path),
    it falls back to a curated per-user seed so known demo identities still get
    a meaningful fingerprint — honestly labelled as curated.

The stylometric/voice agents stay pure and synchronous; the async fetch happens
in the worker before the agents are dispatched, and the samples are passed in.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger(__name__)

# ── Curated per-user baselines (fallback when no live history is available) ─────
# These stand in for "the sender's normal writing" — calm, well-punctuated,
# no urgency. A hijacked-account / impostor message deviates sharply from them,
# which is what the stylometric agent detects. Labelled curated per §13.
_CURATED_BASELINES: dict[str, list[str]] = {
    "U_CEO": [
        "Hi team, thanks for the update. Let's review the Q3 numbers on Thursday "
        "and circle back with finance once we have the full picture.",
        "Appreciate everyone's work this sprint. No rush on the report — end of "
        "next week is fine. Enjoy the weekend.",
        "Good morning. Could you please share the vendor summary when you get a "
        "chance? Happy to discuss on our regular call.",
    ],
    "U_CFO": [
        "Please find the reconciled ledger attached. Everything ties out for the "
        "quarter; let me know if you spot anything unusual.",
        "Thanks for flagging that invoice. I'll route it through the standard "
        "approval workflow and confirm once it clears.",
    ],
    "U_DEMO": [
        "Morning all. Sharing last week's notes here for visibility. Nothing "
        "urgent — just keeping the thread updated as we go.",
        "Thanks for the heads up. Let's keep to the normal process and I'll "
        "follow up after the review meeting.",
    ],
}


def curated_baseline(user_id: str) -> list[str]:
    """Return the curated fallback baseline for a known demo user, or []."""
    return _CURATED_BASELINES.get(user_id, [])


async def fetch_writing_baseline(
    user_id: str,
    channel: Optional[str] = None,
    max_samples: int = 8,
) -> list[str]:
    """Retrieve a user's recent messages as stylometric baseline samples.

    Uses Slack's search API when SLACK_BOT_TOKEN is configured (the MCP-style
    history retrieval), otherwise falls back to the curated seed. Always returns
    a list (possibly empty); never raises.
    """
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token or token.startswith("xoxb-test") or token == "xoxb-not-configured":
        samples = curated_baseline(user_id)
        if samples:
            log.info("mcp_baseline: using curated baseline for %s", user_id)
        return samples

    try:
        import httpx  # type: ignore

        query = f"from:{user_id}"
        if channel:
            query = f"in:{channel} {query}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://slack.com/api/search.messages",
                headers={"Authorization": f"Bearer {token}"},
                params={"query": query, "count": max_samples, "sort": "timestamp"},
            )
            data = resp.json()
        if not data.get("ok"):
            log.warning("mcp_baseline: search error %s — falling back to curated",
                        data.get("error"))
            return curated_baseline(user_id)
        matches = data.get("messages", {}).get("matches", [])
        samples = [m.get("text", "") for m in matches if m.get("text")]
        log.info("mcp_baseline: fetched %d live sample(s) for %s", len(samples), user_id)
        return samples or curated_baseline(user_id)
    except Exception as e:
        log.warning("mcp_baseline: live fetch failed (%s) — using curated", e)
        return curated_baseline(user_id)
