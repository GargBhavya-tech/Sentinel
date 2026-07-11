# Sentinel — Audit Report
**Scope:** full repo (`sentinel/`, `sentinel-frontend/`, infra, tests) · **Date:** 2026-07-11
**Method:** static read of every module + live execution (installed deps, ran full pytest suite, built the frontend, booted the backend, fired real HTTP/SSE traffic against it, reproduced every bug below with a stack trace before proposing a fix).

Baseline from your last audit round (psycopg3 API misuse in `repo.py`) is now fixed — confirmed below. This pass found **3 new bugs** that actually break execution, one of them severe (blocks the officially documented Docker path entirely), plus a handful of hygiene/staleness issues.

---

## 1. Bugs that break execution (verified, reproduced)

### 1.1 🔴 CRITICAL — `pip install -e .` fails, so `docker compose up` can never finish building the backend

`Dockerfile` runs `RUN pip install -e .` after copying source. `pyproject.toml` has a `[project]` table but no `[tool.setuptools.packages.find]`. Modern setuptools (≥61, whatever PyPI resolves today) refuses to guess which top-level directory is the package when it sees more than one candidate at repo root (`sentinel/` and `demo_artifacts/`):

```
error: Multiple top-level packages discovered in a flat-layout: ['sentinel', 'demo_artifacts'].
```

I reproduced this directly (`pip install -e .` inside a clean venv against this exact repo → hard failure, exit code 1). This means the **Quickstart path in your own README (`docker compose up -d`) is currently broken** — the `backend` image never builds.

**Fix** — add to `pyproject.toml`:
```toml
[tool.setuptools.packages.find]
include = ["sentinel*"]
```
Verified: with this added, `pip install -e .` builds and installs cleanly. Takes 30 seconds to apply.

### 1.2 🔴 CRITICAL — the entire React-console demo path is broken when running without Postgres

`sentinel/db/__init__.py` auto-selects `repo_memory.py` (an in-memory stub) when `DATABASE_URL=memory://` — this is your documented zero-Docker way to demo/test. But `repo_memory.py` was never updated when `amount_at_risk` was added (migration `003_amount_at_risk.sql`, and the corresponding `order_by="expected_loss"` triage feature):

- `repo_memory.create_case()` doesn't accept `amount_at_risk` at all.
- `repo_memory.Case` has no `amount_at_risk` field.
- `repo_memory.list_cases()` doesn't accept `order_by`.

Real repro: booted the gateway with `DATABASE_URL=memory://`, hit `POST /api/investigate` with a normal payload (exactly what the React console sends) →

```
TypeError: create_case() got an unexpected keyword argument 'amount_at_risk'
```
→ hard 500, no case ever created. This is **not caught** — `start_investigation()` has no try/except around `repo.create_case(...)`, so every single investigation started from the React console (or `demo_case=true`) 500s immediately in memory mode.

A second, related instance: `GET /cases` *is* wrapped in try/except, so instead of 500ing it silently swallows the `TypeError: list_cases() got an unexpected keyword argument 'order_by'` and returns `{"cases": []}` — meaning even if a case were created, the dashboard queue would permanently show empty with zero indication why. That's a debugging trap: a `except Exception` this broad hides a real signature bug, not just Postgres-down.

**Fix** (verified working end-to-end — I patched it locally, restarted the gateway, and successfully created + streamed an investigation in memory mode):
```python
# repo_memory.py
@dataclass
class Case:
    ...
    verdict: Optional[str] = None
    amount_at_risk: float = 0.0        # ← add
    ...

async def create_case(slack_channel="C_DEMO", slack_ts="", reporter_slack_id="U_DEMO",
                       amount_at_risk=0.0, conn=None) -> Case:   # ← add param
    c = Case(..., amount_at_risk=amount_at_risk)
    _cases[c.case_id] = {..., "amount_at_risk": c.amount_at_risk, ...}
    return c

async def list_cases(limit=20, order_by="recent", conn=None) -> list[Case]:  # ← add param
    if order_by == "expected_loss":
        all_cases = sorted(_cases.values(),
                            key=lambda c: (c.get("risk_score") or 0) * (c.get("amount_at_risk") or 0),
                            reverse=True)
    else:
        all_cases = sorted(_cases.values(), key=lambda c: c.get("created_at", 0), reverse=True)
    ...
```
(also thread `amount_at_risk` through the field-tuples in `get_case`/`list_cases`'s dict→dataclass reconstruction.)

**Why this matters more than a normal bug**: `memory://` mode is your *only* way to demo/test Sentinel without Docker + Postgres. Right now it's decorative — it boots, looks healthy on `/health`, and then silently fails on the one action a judge/tester will actually take.

### 1.3 🟡 Config conflict — `pytest tests/ -v` (exactly what your README tells people to run) doesn't skip integration tests

You have **two** pytest config sources: `pytest.ini` and `pyproject.toml`'s `[tool.pytest.ini_options]`. Pytest gives `pytest.ini` priority when both exist — so `pyproject.toml`'s `addopts = "-m 'not integration'"` is silently ignored. `pytest.ini` has no `addopts` at all.

Result: running the suite exactly as documented, without a live Postgres, gives:
```
FAILED tests/test_gateway.py::test_get_case_404_real_db - psycopg_pool.PoolTimeout
FAILED tests/test_gateway.py::test_audit_verify_empty_chain - psycopg_pool.PoolTimeout
244 passed, 3 skipped, 2 failed in 212s
```
30-second pool timeout each, so it also makes the suite ~1 minute slower than necessary for no reason.

**Fix** — delete `pytest.ini` and let `pyproject.toml` be the single source of truth (or add `addopts = "-m 'not integration'"` to `pytest.ini` and drop the duplicate table from `pyproject.toml`). Either way, pick one file.

**Everything else in the test suite is genuinely solid** — 244/246 non-integration tests pass cleanly, and the 2 failures are 100% explained by the above, not real logic bugs. That's a good signal on the reconciler/eval/agents core.

---

## 2. Confirmed fixed since last audit

- **psycopg3 API misuse** (previous critical finding) — `repo.py` now wraps the raw `AsyncConnection` in a `_ConnAdapter` that gives `fetchone`/`fetchall`/`execute` in the shape the rest of the module expects, and `_noop` correctly re-wraps a caller-supplied connection so transactional call chains behave identically. I read this file end-to-end; the fix is sound and consistent everywhere it's used (12 call sites, all correct).

---

## 3. Stale / dead code, hygiene issues

- **`sentinel-frontend/package.json`** — `"name": "react-example"`, plus dependencies that are 100% unused leftovers from a Google AI Studio scaffold: `@google/genai`, `express`, `dotenv`, `@types/express`. Grepped the entire `src/` tree — zero references. `metadata.json` still declares `"majorCapabilities": ["MAJOR_CAPABILITY_SERVER_SIDE_GEMINI_API"]`, and `sentinel-frontend/.env.example` documents `GEMINI_API_KEY` / `APP_URL` — neither of which the app reads anywhere. Meanwhile the variable the frontend *actually* needs, `VITE_API_URL` (read in `vite.config.ts` to point the dev proxy at the backend), isn't documented in that `.env.example` at all. Low severity, but it's the first thing a reviewer opens and it currently tells them the wrong story about what the app depends on.
- **`federated.py`** — `simulated: bool = True # ALWAYS True for hackathon`. The federated-learning/cross-org signal-sharing feature is fully mocked, not a real integration. Fine for a hackathon submission, but worth stating explicitly in the README's feature table rather than only in a source comment, since right now nothing in the "What's Built" table signals that this one is simulated while the others are real.
- Frontend production bundle is a single 587 KB chunk (187 KB gzip) — not a bug, but `vite build` warns about it. Not worth fixing before a demo; worth a `manualChunks` pass later if this becomes a real product.

---

## 4. How to actually test it (not terminal output — the real Slack + React UI)

Two paths. Given finding 1.1, **path A currently requires the one-line `pyproject.toml` fix above** before `docker compose up` will build. Path B works today with the fix in 1.2 applied (or you can wait for me to apply both and hand you a patched zip).

### Path A — Docker (real Postgres, closest to production)

1. Apply the `[tool.setuptools.packages.find]` fix to `pyproject.toml` (§1.1).
2. `cp .env.example .env`, fill in `PII_HMAC_PEPPER` (`python -c "import secrets;print(secrets.token_hex(32))"`). Slack keys optional — leaving them as placeholders keeps Slack in "inert mode" (REST/SSE still work).
3. `docker compose up -d --build`
4. Open **http://localhost:3000** in your browser — that's the actual React console (`sentinel-frontend`), not a terminal. It's served by the `frontend` service (Vite dev server) which proxies `/api`, `/cases`, `/graph`, `/audit`, `/health` to the backend container on port 8000, so there's no CORS setup needed.
5. In the UI: use the investigation form (or the "demo case" trigger — `demo_case: true` in the payload, which the console likely exposes as a button/toggle in `EvidenceSubmitModal.tsx`) to fire `POST /api/investigate`. Watch the live SSE stream render in `LiveInvestigation.tsx` / `DashboardConsole.tsx` as agents complete, contradictions surface, and a verdict posts.
6. Cross-check against Postgres directly if you want: `docker compose exec db psql -U sentinel -d sentinel -c "select * from cases;"`.
7. For the actual Slack integration (not just the React console), you still need ngrok + a Slack app per the README's steps 3–5 — that part of the README is accurate and untouched by anything in this audit.

### Path B — No Docker, browser UI against the in-memory backend (fastest loop, good for iterating on frontend/agent logic)

1. Apply the `repo_memory.py` fix in §1.2 (or ask me and I'll hand you the patched files).
2. `pip install -r requirements.txt`
3. `.env`: set `DATABASE_URL=memory://`, set a real `PII_HMAC_PEPPER`. Leave Slack keys unset.
4. Terminal 1: `uvicorn sentinel.gateway:api --reload` (backend on :8000)
5. Terminal 2: `cd sentinel-frontend && npm install && npm run dev` (frontend on :3000, `VITE_API_URL` defaults to `http://localhost:8000` when unset — no env var needed for this path)
6. Open **http://localhost:3000** — same real UI as Path A, just backed by an in-process Python dict instead of Postgres. Data resets every backend restart, which is exactly what you want for a fast test loop.
7. This is the path I actually exercised: booted the gateway this way, POSTed a real investigation payload through the API the console uses, watched it 500 pre-fix and succeed post-fix, confirmed the case round-trips through `GET /cases` and `GET /cases/{id}`.

Either path gets you off the terminal and into the actual dashboard/investigation UI — Path A is closer to what a judge/production deploy looks like, Path B is faster for iterating since there's no container rebuild step.

---

## 5. Bottom line

- Core logic (reconciler, eval harness, rules engine, agents) is solid — 244 passing tests, no red flags reading through them.
- The DB layer's real-Postgres path (`repo.py`) is correctly fixed from last time.
- Three real, previously-unflagged bugs currently sit between a fresh clone and a working demo: a broken Docker build (`pyproject.toml` packaging config), a broken no-Docker demo path (`repo_memory.py` drift on `amount_at_risk`/`order_by`), and a pytest config conflict that makes `pytest tests/ -v` fail exactly as documented. All three are small, mechanical fixes (I verified all three fixes work) — total maybe 20 minutes of work — but as-is they mean **neither of the two ways to run this project currently works out of the box**, which is worth knowing before you point anyone (WSL, a recruiter, a hackathon judge) at the README.
