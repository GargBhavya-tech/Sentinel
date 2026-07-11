"""FastAPI application — the async Slack + React gateway (build-map ticket #1).

Responsibilities
----------------
1. Mount the Slack Bolt ASGI app on `POST /slack/events`.
2. ACK every Slack webhook inside Slack's 3-second window.
3. Hand heavy work to `BackgroundTasks` (never do it in-handler).
4. Expose REST + SSE endpoints for the React console and judges.

Routes
------
  POST /slack/events                     — Slack webhook (Bolt handles internally)
  GET  /health                           — liveness probe
  GET  /cases/{case_id}                  — fetch a case by ID
  GET  /cases                            — list recent cases
  GET  /cases/{case_id}/audit            — audit chain for a case
  POST /api/investigate                  — start investigation from React console
  GET  /api/investigate/{case_id}/stream — SSE stream of investigation events
  GET  /api/rules                        — list shadow/enforced rules
  POST /api/rules/{rule_id}/promote      — promote shadow rule to enforced
  GET  /api/metrics                      — eval harness metrics (ticket #34)
  GET  /api/active-learning/status       — active learning status (ticket #28)
  POST /api/active-learning/label        — submit human label (ticket #28)
  GET  /graph/snapshot                   — current graph cache as JSON
  GET  /audit/verify                     — verify the hash-chained audit log
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler  # type: ignore

# ── env & logging ─────────────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

# ── deferred imports (need env loaded first) ──────────────────────────────────
from sentinel.db import close_db_pool, get_db_pool  # noqa: E402
from sentinel.db import repo  # noqa: E402
from sentinel.graph.cache import get_graph_snapshot  # noqa: E402
from sentinel.slack_app import app as bolt_app  # noqa: E402
from sentinel.worker import investigate  # noqa: E402
from sentinel.sse_worker import (  # noqa: E402
    investigate_streaming,
    create_case_queue,
    get_case_queue,
)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(api: FastAPI):
    """Open DB pool on startup; close on shutdown."""
    log.info("Sentinel gateway starting — opening DB pool…")
    _pepper = os.environ.get("PII_HMAC_PEPPER", "")
    if _pepper in ("", "change-me-to-a-strong-random-value"):
        log.warning(
            "PII_HMAC_PEPPER is unset/default — PII pseudonymization is NOT "
            "secure. Set a strong random value (python -c \"import secrets; "
            "print(secrets.token_hex(32))\")."
        )
    await get_db_pool()
    log.info("DB pool ready.")
    # Apply idempotent SQL migrations so an existing Postgres volume picks up
    # 002/003 without manual psql (docker-entrypoint only runs them on a fresh
    # volume). No-ops in memory:// mode.
    try:
        from sentinel.db.migrate import run_migrations

        await run_migrations()
    except Exception as e:
        log.warning("startup migrations skipped: %s", e)
    yield
    log.info("Sentinel gateway shutting down — closing DB pool…")
    await close_db_pool()


# ── FastAPI app ───────────────────────────────────────────────────────────────
api = FastAPI(
    title="Sentinel Gateway",
    version="0.2.0",
    description="Slack-native fraud investigator — gateway + React console API",
    lifespan=lifespan,
)

# CORS — default to the Vite dev servers; override via CORS_ORIGINS (comma-sep).
# Note: a wildcard origin with allow_credentials=True is rejected by browsers,
# so we enumerate origins explicitly. The Vite proxy makes calls same-origin in
# dev, so this rarely even engages locally.
_cors_origins = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")
    if o.strip()
]
api.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

handler = AsyncSlackRequestHandler(bolt_app)


def require_console_key(x_sentinel_key: str = Header(default="")) -> None:
    """Optional shared-secret guard for state-changing endpoints.

    Enforced ONLY when the CONSOLE_KEY env var is set, so the local demo works
    with zero config, but a deployed/judge-facing instance can lock down writes
    (e.g. rule promotion) by setting CONSOLE_KEY and sending X-Sentinel-Key.
    """
    required = os.environ.get("CONSOLE_KEY")
    if required and x_sentinel_key != required:
        raise HTTPException(status_code=401, detail="unauthorized")


# ── Request models ────────────────────────────────────────────────────────────

class InvestigateRequest(BaseModel):
    description: str = "suspicious invoice"
    amount_at_risk: float = 0.0
    file_url: str | None = None
    evidence_id: str | None = None    # from POST /api/upload (browser drag-drop)
    channel: str = "C_DEMO"
    reporter: str = "U_DEMO"
    demo_case: bool = False           # load the flagship demo case signals


class LabelRequest(BaseModel):
    case_id: str
    label: int                        # 0 = legitimate, 1 = fraud


# ── Slack events endpoint ─────────────────────────────────────────────────────

@api.post("/slack/events")
async def slack_events(req: Request, background_tasks: BackgroundTasks) -> Response:
    """Receive Slack webhook, ACK <5ms, queue background work."""
    # Read the body ONCE, before Bolt consumes the request stream. Starlette
    # caches the body after the first read, so Bolt's handler still sees it for
    # signature verification. Reading it twice (the old order) was fragile and
    # order-dependent.
    body: dict = {}
    if req.headers.get("content-type") == "application/json":
        try:
            body = await req.json()
        except Exception:  # malformed / empty body — let Bolt reject it
            body = {}

    bolt_resp = await handler.handle(req)

    event = body.get("event", {})
    if (
        event.get("type") == "app_mention"
        and "investigate" in event.get("text", "").lower()
    ):
        background_tasks.add_task(investigate, event)
        log.info("Investigation enqueued for ts=%s", event.get("ts"))

    return bolt_resp


# ── React Console: Start investigation ────────────────────────────────────────

@api.post("/api/upload")
async def upload_evidence(file: UploadFile = File(...)) -> dict:
    """Accept a browser file upload and return an evidence_id.

    The client passes that id back to /api/investigate; the worker resolves it
    to the stored file so the Vision agent analyzes the real document.
    """
    from sentinel.ingest import save_upload

    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file too large (max 15 MB)")
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    evidence_id = save_upload(data, file.filename or "upload.bin")
    return {"evidence_id": evidence_id, "filename": file.filename}


# ── Simple in-memory rate limiter for /api/investigate ─────────────────────────
import time as _time
from collections import defaultdict, deque

_RATE_WINDOW_S = 60.0
_RATE_MAX = int(os.environ.get("INVESTIGATE_RATE_MAX", "30"))  # per IP per minute
_rate_hits: dict[str, deque] = defaultdict(deque)


def _rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = _time.monotonic()
    dq = _rate_hits[ip]
    while dq and now - dq[0] > _RATE_WINDOW_S:
        dq.popleft()
    if len(dq) >= _RATE_MAX:
        raise HTTPException(status_code=429, detail="rate limit exceeded — slow down")
    dq.append(now)


@api.post("/api/investigate")
async def start_investigation(
    body: InvestigateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> dict:
    """Start a Sentinel investigation from the React console.

    Returns the case_id immediately. The client then subscribes to
    GET /api/investigate/{case_id}/stream to receive SSE events.
    """
    _rate_limit(request)

    # Resolve the description + amount first (demo override), so the case row
    # persists the amount_at_risk used for expected-loss triage (#24).
    description = body.description
    amount = body.amount_at_risk
    if body.demo_case:
        from sentinel.demo_fixtures import DEMO_DESCRIPTION, DEMO_AMOUNT

        description = DEMO_DESCRIPTION
        amount = DEMO_AMOUNT

    # Create DB case
    case = await repo.create_case(
        slack_channel=body.channel,
        slack_ts=str(uuid.uuid4()),
        reporter_slack_id=body.reporter,
        amount_at_risk=amount,
    )
    log.info("React console investigation started — case %s", case.case_id[:8])

    # Create SSE queue before launching background task
    q = create_case_queue(case.case_id)

    # Resolve an uploaded file (evidence_id) to its stored path; fall back to a
    # directly-supplied file_url. The worker's download_evidence handles both.
    file_ref = body.file_url
    if body.evidence_id:
        from sentinel.ingest import resolve_upload

        file_ref = resolve_upload(body.evidence_id) or body.file_url

    # Launch streaming worker as background task
    background_tasks.add_task(
        investigate_streaming,
        case_id=case.case_id,
        q=q,
        event_text=description,
        amount_at_risk=amount,
        channel=body.channel,
        reporter=body.reporter,
        file_url=file_ref,
        demo_case=body.demo_case,
    )

    return {
        "case_id": case.case_id,
        "short_id": case.case_id[:8],
        "stream_url": f"/api/investigate/{case.case_id}/stream",
        "status": "started",
    }


# ── React Console: SSE stream ─────────────────────────────────────────────────

@api.get("/api/investigate/{case_id}/stream")
async def stream_investigation(case_id: str) -> StreamingResponse:
    """Server-Sent Events stream for a running investigation.

    The client opens this with EventSource. Events are JSON objects with
    `event` (type string) and `data` (payload dict) fields.

    The stream ends when a `stream_end` event is received.
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        # Wait up to 10s for the queue to appear (background task may not have
        # started yet when the client connects immediately after POST)
        for _ in range(100):
            q = get_case_queue(case_id)
            if q is not None:
                break
            await asyncio.sleep(0.1)
        else:
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': 'Case queue not found'}})}\n\n"
            return

        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # Keepalive comment to prevent connection drop
                yield ": keepalive\n\n"
                continue

            if item is None:
                break

            event_type = item.get("event", "data")
            payload = json.dumps(item)
            yield f"event: {event_type}\ndata: {payload}\n\n"

            if event_type == "stream_end":
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── REST endpoints ────────────────────────────────────────────────────────────

@api.get("/health")
async def health() -> dict:
    """Liveness probe — returns 200 + service info when the server is up."""
    return {"status": "ok", "service": "sentinel-gateway", "version": "0.2.0"}


@api.get("/cases/{case_id}")
async def get_case(case_id: str) -> dict:
    """Fetch a case by ID for the React console."""
    case = await repo.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id!r} not found")
    from dataclasses import asdict
    return asdict(case)


@api.get("/cases")
async def list_cases(limit: int = 20, order_by: str = "recent") -> dict:
    """List cases for the dashboard queue.

    order_by="expected_loss" ranks by risk × amount_at_risk (triage by $ exposure).
    """
    try:
        cases = await repo.list_cases(limit=limit, order_by=order_by)
        return {
            "cases": [
                {
                    "case_id": c.case_id,
                    "short_id": c.case_id[:8],
                    "status": c.status,
                    "verdict": c.verdict,
                    "risk_score": c.risk_score,
                    "amount_at_risk": c.amount_at_risk,
                    "expected_loss": round((c.risk_score or 0) * (c.amount_at_risk or 0), 2),
                    "created_at": str(c.created_at) if hasattr(c, "created_at") else "",
                }
                for c in cases
            ]
        }
    except Exception as e:
        log.warning("list_cases failed: %s", e)
        return {"cases": []}


@api.get("/cases/{case_id}/audit")
async def get_audit_chain(case_id: str) -> dict:
    """Return the audit chain for a specific case."""
    try:
        chain = await repo.get_audit_chain(case_id)
        return {"case_id": case_id, "entries": chain}
    except Exception as e:
        log.warning("get_audit_chain failed: %s", e)
        return {"case_id": case_id, "entries": []}


@api.get("/api/rules")
async def list_rules() -> dict:
    """List shadow and enforced detection rules."""
    try:
        rules = await repo.list_rules()
        return {
            "rules": [
                {
                    "rule_id": r.rule_id if hasattr(r, "rule_id") else r.get("rule_id", ""),
                    "description": r.description if hasattr(r, "description") else r.get("description", ""),
                    "status": r.status if hasattr(r, "status") else r.get("status", "shadow"),
                    "created_at": str(r.created_at) if hasattr(r, "created_at") else "",
                }
                for r in rules
            ]
        }
    except Exception as e:
        log.warning("list_rules failed: %s", e)
        return {"rules": []}


@api.post("/api/rules/{rule_id}/promote")
async def promote_rule(rule_id: str, _: None = Depends(require_console_key)) -> dict:
    """Promote a shadow rule to enforced status."""
    try:
        await repo.promote_rule(rule_id)
        await repo.append_audit_event(
            case_id="system",
            event_type="rule_promoted",
            payload={"rule_id": rule_id, "new_status": "enforced"},
        )
        return {"rule_id": rule_id, "status": "enforced", "message": "Rule promoted to enforced."}
    except Exception as e:
        log.error("promote_rule failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/api/metrics")
async def get_metrics() -> dict:
    """Run eval harness and return precision/recall/F1 + ablation numbers."""
    try:
        from sentinel.eval.harness import ablation, headline_number
        a = ablation()
        headline = headline_number()
        return {
            "headline": headline,
            "engine_on": a["on"],
            "engine_off": a["off"],
            "recall_gain": a["recall_gain"],
            "frauds_caught_by_engine_only": a["frauds_caught_by_engine_only"],
            "n_caught_by_engine_only": a["n_caught_by_engine_only"],
            "total_cases": a["n"],
        }
    except Exception as e:
        log.warning("metrics failed: %s", e)
        return {"error": str(e)}


@api.get("/api/active-learning/status")
async def active_learning_status() -> dict:
    """Return the current active-learning status (ticket #28)."""
    from sentinel.eval.active_learning import get_status
    return get_status()


@api.post("/api/active-learning/label")
async def submit_label(body: LabelRequest) -> dict:
    """Submit a human label for an uncertain case (ticket #28)."""
    from sentinel.eval.active_learning import submit_label, compute_accuracy_lift
    result = submit_label(body.case_id, body.label)
    lift = compute_accuracy_lift()
    return {**result, "accuracy_lift": lift.__dict__}


@api.get("/graph/snapshot")
async def graph_snapshot() -> dict:
    """Return the current in-memory graph as JSON for the force-directed UI."""
    return get_graph_snapshot()


@api.get("/audit/verify")
async def audit_verify() -> dict:
    """Walk the audit chain and verify no entry has been tampered with."""
    ok, message = await repo.verify_audit_chain()
    return {"intact": ok, "message": message}


# ── Mount Frontend ────────────────────────────────────────────────────────────

from fastapi.staticfiles import StaticFiles

_frontend_dir = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "sentinel-frontend", "dist"
)
if os.path.exists(_frontend_dir):
    api.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")


# ── Dev entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "sentinel.gateway:api",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
