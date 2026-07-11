# Sentinel — Testing & Verification Guide

This is the checklist to run before you consider any build "done" — for a
feature branch, a PR, or the final submission. It covers automated tests,
manual verification, security checks, and the known-bug regression suite
from `Sentinel_Debug_Report.md`.

Work through it top to bottom. Don't skip straight to the manual Slack demo —
most things are cheaper to catch in the earlier sections.

---

## 0. Before you start — environment setup

```bash
# Fresh virtualenv every time you're verifying a release candidate.
# Reusing a dirty venv hides missing-dependency bugs (see report #4).
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install ruff  # for static analysis, not in requirements.txt on purpose
```

**Sanity check the install itself:**
```bash
python3 -c "from sentinel.gateway import api"
```
If this fails with `ModuleNotFoundError`, the fix belongs in `requirements.txt`,
not in your local venv. Do not `pip install` the missing package locally and
move on — that just hides the bug for the next person.

---

## 1. Static analysis (fastest signal, run first)

```bash
ruff check sentinel/ tests/ run_case.py run_eval.py run_self_play.py --select=E9,F
```
- `E9` = syntax errors. Zero tolerance — must be empty output.
- `F` = pyflakes (unused imports, undefined names, redefinitions). Unused
  imports (`F401`) are okay to leave for a WIP branch but must be clean
  before merging to `main`.

Specifically watch for:
- `F821` (undefined name) — zero tolerance, always a real bug.
- `F841` (unused variable) — usually a sign of a half-finished refactor.

---

## 2. Automated test suite

```bash
pytest tests/ -v
```

Expected: **all non-integration tests pass**. As of the last audit this is
228/230, with the 2 failures being `@pytest.mark.integration` tests that
need a live Postgres (see §3).

**Register the marker** before running, to avoid noise:
```ini
# pytest.ini
[pytest]
pythonpath = .
asyncio_mode = auto
markers =
    integration: requires a live Postgres (docker compose up -d)
```

If you added new agent logic or touched the reconciler, also run with
coverage so gaps are visible, not just green/red:
```bash
pip install pytest-cov
pytest tests/ --cov=sentinel --cov-report=term-missing
```

### 2a. Known-bug regression suite
`tests/test_debug_report_findings.py` (already handed to the team) encodes
the 5 issues from the debug report as real, runnable tests:

```bash
pytest tests/test_debug_report_findings.py -v
```

- A test going from **RED → GREEN** is your confirmation that a specific
  fix actually landed — don't just trust the PR description, run the test.
- **Never delete or weaken an assertion in this file to make it pass.**
  If a test seems wrong, that's a conversation, not a quiet edit.
- When all 5 are green, delete the file's `[RED until ...]` docstring
  labels (or just fold the tests into the main suite) — they've graduated
  from bug-reproduction to permanent regression guards.

---

## 3. Integration tests (real Postgres)

These are the only tests that touch `sentinel/db/repo.py` for real, which is
where the most serious bug in the report lives. Do not consider the DB layer
verified until these pass.

```bash
docker compose up -d
# wait a few seconds for Postgres + the 001_initial.sql migration to apply
pytest tests/ -v -m integration
```

Manually confirm state in the DB, don't just trust the test's assertion:
```bash
psql postgresql://sentinel:sentinel@localhost:5432/sentinel -c "SELECT * FROM cases ORDER BY created_at DESC LIMIT 5;"
psql postgresql://sentinel:sentinel@localhost:5432/sentinel -c "SELECT * FROM audit_chain ORDER BY entry_id DESC LIMIT 5;"
```

If `repo.py`'s connection-API bug (#1 in the debug report) hasn't been
fixed yet, these tests will fail with `AttributeError`, not just a
timeout — re-run once you've confirmed Postgres is actually reachable
(`docker compose ps`) before assuming it's the known bug.

---

## 4. Manual end-to-end verification (Slack)

Automated tests don't cover the actual Slack round-trip. Do this once per
release candidate, not once per PR.

1. Follow README §3–5 to stand up a real dev Slack app + ngrok tunnel.
2. In a channel with the bot installed, type `@Sentinel investigate`.
3. **Timing check**: the "investigating…" ack card must appear in **under
   ~1 second**. If it's slow, something heavy has leaked into the Bolt
   handler instead of the background worker — check `slack_app.py` and
   `gateway.py`'s `BackgroundTasks` usage.
4. Confirm a verdict card posts to the same thread once the worker
   finishes.
5. Confirm a new row exists: `SELECT * FROM cases;`
6. Run the flagship "contradiction-only" demo case and confirm the verdict
   differs from what `contradiction_engine="off"` would produce — this is
   the core pitch, so it's worth explicitly diffing `on` vs `off` (see
   `run_eval.py` / the eval harness) rather than eyeballing one card.
7. Try at least one **thin-evidence** case (1 claim, or claims with low
   confidence). Until report item #2 is fixed, expect this to incorrectly
   resolve as `CLEAR` — track this as a known limitation until the fix
   lands, don't let it surprise you during a live demo.

---

## 5. Security / config checklist

Run through this before any deploy, not just once:

- [ ] `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `DATABASE_URL`,
      `PII_HMAC_PEPPER` are all set to real values — confirm the app
      **fails to start** if any are missing, rather than booting with
      empty-string defaults. If it boots silently, that's report item #5,
      unfixed.
- [ ] CORS: `allow_origins` is either an explicit list, or
      `allow_credentials=False`. Never both `["*"]` and `True` — see report
      item #3. Check with:
      ```python
      from sentinel.gateway import api
      for m in api.user_middleware:
          if "CORS" in str(m.cls):
              print(m.kwargs)
      ```
- [ ] `PII_HMAC_PEPPER` is a real random value (`python -c "import secrets;
      print(secrets.token_hex(32))"`), not the `.env.example` placeholder.
- [ ] No secrets committed anywhere — `git grep -i "xoxb-\|xapp-\|SLACK_SIGNING_SECRET *="` on tracked files before every push.
- [ ] `.env` is in `.gitignore` (check, don't assume).

---

## 6. Data-layer specific checks

Because `repo.py` is the single highest-risk file in the codebase right now:

- [ ] Every function in `sentinel/db/repo.py` uses `cur = await
      c.execute(sql, params)` followed by `await cur.fetchone()` /
      `await cur.fetchall()` — **not** `c.fetchone(...)` /
      `c.fetchall(...)` directly on the connection.
- [ ] `test_create_case_uses_real_psycopg_connection_api` in the regression
      suite is green.
- [ ] All SQL remains parameterized (`%s` placeholders passed as a tuple,
      never f-string/`.format()`-built queries). Quick audit:
      ```bash
      grep -n 'f"\|f'"'"'\|\.format(' sentinel/db/repo.py
      ```
      Should return nothing that constructs SQL text dynamically from
      user-controlled input.

---

## 7. Sign-off criteria (what "done" means)

A build is ready to demo/submit only when **all** of the following are true:

1. `ruff check` on `E9,F` is clean.
2. `pytest tests/ -v` — all non-integration tests pass.
3. `pytest tests/ -v -m integration` — passes against a real, freshly
   started `docker compose up -d` Postgres.
4. `pytest tests/test_debug_report_findings.py -v` — every test that
   corresponds to a bug you've claimed to fix is green. (It's fine for
   #18-related tests to still be red if that ticket is intentionally
   deferred — just don't claim it's shipped in the pitch docs if so.)
5. Manual Slack walkthrough (§4) completed on the actual demo workspace,
   not just localhost.
6. Security checklist (§5) fully checked.
7. No `TODO`/`FIXME` left in files touched by the current PR without a
   corresponding tracked ticket:
   ```bash
   git diff main --name-only | xargs grep -n "TODO\|FIXME" 2>/dev/null
   ```

If any item fails, it's not done — fix it or explicitly downgrade the
claim in the README/pitch docs to match reality.
