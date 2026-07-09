"""FastAPI application — the async Slack gateway (build-map ticket #1).

Responsibilities
----------------
1. Mount the Slack Bolt ASGI app on `POST /slack/events` so Slack can reach
   the app over HTTP.
2. ACK every webhook inside Slack's 3-second window.
3. Hand heavy work to `BackgroundTasks` (never do it in-handler).
4. Expose REST endpoints for the React console and judges.

Routes
------
  POST /slack/events        — Slack webhook (Bolt handles internally)
  GET  /health              — liveness probe
  GET  /cases/{case_id}     — fetch a case by ID (for the React console)
  GET  /graph/snapshot      — current graph cache as JSON (for the force-directed UI)
  GET  /audit/verify        — verify the hash-chained audit log is intact

Startup / shutdown
------------------
The FastAPI lifespan context manager opens the DB pool on startup and
closes it on shutdown, so every request has a ready connection.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler  # type: ignore

# ── env & logging ─────────────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

# ── deferred imports (need env loaded first) ──────────────────────────────────
from sentinel.db import close_db_pool, get_db_pool
from sentinel.db import repo
from sentinel.graph.cache import get_graph_snapshot
from sentinel.slack_app import app as bolt_app
from sentinel.worker import investigate

# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(api: FastAPI):
    """Open DB pool on startup; close on shutdown."""
    log.info("Sentinel gateway starting — opening DB pool…")
    await get_db_pool()
    log.info("DB pool ready.")
    yield
    log.info("Sentinel gateway shutting down — closing DB pool…")
    await close_db_pool()

# ── FastAPI app ───────────────────────────────────────────────────────────────
api = FastAPI(
    title="Sentinel Gateway",
    version="0.1.0",
    description="Slack-native fraud investigator — Phase 0 gateway",
    lifespan=lifespan,
)

handler = AsyncSlackRequestHandler(bolt_app)


# ── Slack events endpoint ─────────────────────────────────────────────────────

@api.post("/slack/events")
async def slack_events(req: Request, background_tasks: BackgroundTasks) -> Response:
    """Receive Slack webhook, ACK < 5ms, queue background work.

    Bolt's handler verifies the HMAC-SHA256 signature and dispatches to the
    correct Bolt listener. The `app_mention` listener in slack_app.py posts
    the immediate acknowledgement card, then this function enqueues the real
    investigation worker.
    """
    # Bolt processes the request; this handles sig verification + event routing.
    bolt_resp = await handler.handle(req)

    # If it's an app_mention, fire the investigation out-of-band
    body = await req.json() if req.headers.get("content-type") == "application/json" else {}
    event = body.get("event", {})
    if event.get("type") == "app_mention" and "investigate" in event.get("text", "").lower():
        background_tasks.add_task(investigate, event)
        log.info("Investigation enqueued for ts=%s", event.get("ts"))

    return bolt_resp


# ── REST endpoints ────────────────────────────────────────────────────────────

@api.get("/health")
async def health() -> dict:
    """Liveness probe — returns 200 + service info when the server is up."""
    return {"status": "ok", "service": "sentinel-gateway", "version": "0.1.0"}


@api.get("/cases/{case_id}")
async def get_case(case_id: str) -> dict:
    """Fetch a case by ID for the React console."""
    case = await repo.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id!r} not found")
    from dataclasses import asdict
    return asdict(case)


@api.get("/graph/snapshot")
async def graph_snapshot() -> dict:
    """Return the current in-memory graph as JSON for the force-directed UI."""
    return get_graph_snapshot()


@api.get("/audit/verify")
async def audit_verify() -> dict:
    """Walk the audit chain and verify no entry has been tampered with."""
    ok, message = await repo.verify_audit_chain()
    return {"intact": ok, "message": message}


# ── Dev entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "sentinel.gateway:api",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
