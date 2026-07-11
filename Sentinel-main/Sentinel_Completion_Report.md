# Sentinel — Build-Map Completion Report

Cross-checked against `Sentinel_Build_Map.md` ticket-by-ticket: does the code
exist, does it have tests, do those tests pass, and does it actually work
end-to-end (not just in isolation with a mocked DB). Where a bug from
`Sentinel_Debug_Report.md` affects a ticket's real-world status, it's called
out explicitly — a ticket can have code and green tests and still not "work"
if it depends on the broken DB layer.

**Headline:** 30 of 36 tickets have working code + passing tests. 2 CORE
tickets are code-complete but *not actually functional end-to-end* because
of Debug Report bugs. 1 CORE ticket has no code at all (#33). 2 CORE tickets
are non-code deliverables not yet started (#35, #36). 4 open planning
decisions (D1–D4) are still unresolved.

---

## Status legend
- ✅ **Done** — code exists, tests pass, works end-to-end.
- ⚠️ **Built but broken** — code + tests exist, but a known bug (see debug
  report) means it doesn't actually work against a real backend.
- 🟡 **Partial / simplified-by-design** — working, but a scoped-down version
  of the original ask (documented as intentional in the code itself).
- ❌ **Not started** — no code, or not applicable to this repo.

---

## Phase 0 — Foundations

| # | Ticket | Priority | Status | Note |
|---|---|---|---|---|
| 1 | Async Slack Gateway | 🟥 CORE | ✅ Done | Works; note `aiohttp` missing from `requirements.txt` (debug report #4) breaks a clean install until fixed. |
| 2 | Database & Case Lifecycle | 🟥 CORE | ⚠️ **Built but broken** | Schema/migration present, `repo.py` fully written — but every function calls `.fetchone()`/`.fetchall()` directly on a connection object that doesn't have those methods (debug report #1). **Nothing that touches Postgres actually works yet.** Highest-priority fix in the whole project. |
| 3 | Local Graph Cache | 🟥 CORE | ✅ Done | Tested, passing. |

## Phase 1 — Ingestion & Safety

| # | Ticket | Priority | Status | Note |
|---|---|---|---|---|
| 4 | PII Redaction Gateway | 🟥 CORE | ✅ Done | Tested. Fails fast on missing pepper — good pattern, should be copied elsewhere (see #1/#5 in debug report). |
| 5 | File Forensics Pre-Pass | 🟥 CORE | ✅ Done | Tested. |
| 6 | Prompt-Injection Scanner | 🟥 CORE | ✅ Done | Tested. |

## Phase 2 — Specialist Agents

| # | Ticket | Priority | Status | Note |
|---|---|---|---|---|
| 7 | Vision/OCR + Layout Agent | 🟥 CORE | ✅ Done* | Tested. *Regex/heuristic extraction, not an LLM call — see "Agents are heuristic, not LLM-backed" below. |
| 8 | Finance Agent | 🟨 SUPPORTING | ✅ Done* | Same caveat. |
| 9 | NLP Agent | 🟨 SUPPORTING | ✅ Done* | Same caveat. |
| 10 | Threat-Intel Agent | 🟨 SUPPORTING | ✅ Done | Only agent hitting a real external API (VirusTotal). |
| 11 | Stylometric Agent | 🟥 CORE | ✅ Done* | Same caveat. |
| 12 | Voice Authenticity Agent | 🟥 CORE (headline beat) | ✅ Done* | Same caveat, plus **decision D2** (which anti-spoofing model) is still open — check whether the shipped version is the linguistic-acoustic-mismatch fallback the build map allows, or a real spoof classifier. |
| 13 | Compliance Agent | 🟨 SUPPORTING | ✅ Done* | Same caveat. |
| 14 | Policy/Authority Agent | 🟨 SUPPORTING | ✅ Done* | Same caveat. |

**Agents are heuristic, not LLM-backed.** `mock_agents.py`'s own docstring is explicit about this: *"In the real system these are LLM-backed specialists... Here they are deterministic stand-ins."* No file in `sentinel/` calls OpenAI, Anthropic, or any other LLM API (checked project-wide) except `threat_intel_agent.py`'s VirusTotal lookup. For a "multi-agent" pitch, this is the single biggest gap between the narrative and the implementation — worth a conscious decision (ship as-is and describe it accurately, or wire in real model calls before submission) rather than an oversight discovered by a judge.

## Phase 3 — The Reconciler

| # | Ticket | Priority | Status | Note |
|---|---|---|---|---|
| 15 | 3-Way Contradiction Engine | 🟥 CORE ("this is the product") | ✅ Done | Solid — deterministic, readable, tested. The strongest part of the codebase. |
| 16 | Red-Team Sub-Agent | 🟨 SUPPORTING | ✅ Done | Tested. |
| 17 | Adversarial Self-Play | 🟨 SUPPORTING | ✅ Done | `run_self_play.py` entrypoint present. |
| 18 | Confidence-Calibrated Silence | 🟨 SUPPORTING | ❌ **Not implemented** | `Claim.confidence` is never read anywhere in `reconciler.py`/`pipeline.py`. No "uncertain/need more info" verdict exists. The pitch docs (Winning Edition Bible §8, Master Reference) describe this as shipped — it isn't. The only artifact is a root-level `test_silence.py` with no assertions, not part of the test suite. See debug report #2. |

## Phase 4 — Graph & Propagation

| # | Ticket | Priority | Status | Note |
|---|---|---|---|---|
| 19 | BFS Blast-Radius Mapper | 🟥 CORE | ✅ Done | Tested. |
| 20 | Graph Analytics (PageRank + Components) | 🟥 CORE | ✅ Done | Tested. |
| 21 | Temporal Recall | 🟥 CORE | 🟡 Partial | Working, but uses a "lightweight hash-based bag-of-words embedding" per its own docstring, not the sentence-transformers + pgvector combo **decision D4** defaults to. Fine as a demo stand-in; flag it if a judge asks about the embedding model. |
| 22 | Active Quarantine | 🟨 SUPPORTING | ✅ Done | Tested. |
| 23 | Campaign Clustering | 🟨 SUPPORTING | ✅ Done | Tested. |
| 24 | Fraud Economics + Expected-Loss Triage | 🟨 SUPPORTING | ✅ Done | Implemented as an MCP tool (`_tool_expected_loss`) + `_compute_expected_loss()` in `sse_worker.py`, not a standalone module — that's fine, just worth knowing where to find it. |
| 25 | Scripted Honeypot | 🟨 SUPPORTING | ✅ Done | Tested. |

## Phase 5 — Learning Loop

| # | Ticket | Priority | Status | Note |
|---|---|---|---|---|
| 26 | Self-Writing Detection Rules | 🟥 CORE (closing beat) | ⚠️ **Built but broken** | `rules/engine.py`, `synthesizer.py`, `schema.py` all present and unit-tested — but the shadow→enforced lifecycle (`save_rule`, `list_rules`, `promote_rule`) persists through `repo.py`, so it inherits bug #1 and won't actually work against Postgres yet. |
| 27 | Hash-Chained Audit Log | 🟥 CORE | ⚠️ **Built but broken** | Logic (`append_audit_event`, `verify_audit_chain`) is in `repo.py` — same story as #2/#26. The audit chain design itself looks sound; it just can't run yet. |
| 28 | Active-Learning Loop | 🟨 SUPPORTING | ✅ Done* | Endpoints + logic present and tested. *Currently effectively in-memory since it also routes through the same DB layer for persistence in places — re-verify once #1 is fixed. |
| 29 | Federated Pattern Network | ⬜ FAKE/SEED (by design) | ✅ Done, as specified | Explicitly meant to be a simulated/seeded demo per the build map, and that's exactly what's implemented — no gap here. |

## Phase 6 — Server, UI, Trust

| # | Ticket | Priority | Status | Note |
|---|---|---|---|---|
| 30 | Sentinel as an MCP Server | 🟥 CORE (tech-depth differentiator) | ✅ Done | 411-line implementation, dedicated test file, 11/11 tests passing. |
| 31 | Slack Block Kit UI | 🟥 CORE (Best UX bid) | ✅ Done | Block Kit usage present in `slack_app.py` and `worker.py`. |
| 32 | React Investigation Console | 🟥 CORE (Best UX bid) | ✅ Done | Full `sentinel-frontend/` app with dashboard, live investigation view, evidence modal, etc. (Not covered by the Python test suite — no automated frontend tests exist; verify this manually per the testing guide.) |
| 33 | Slack Canvas Case File | 🟨 SUPPORTING | ❌ **Not started** | No reference to Slack Canvas anywhere in the codebase (`grep -rn "canvas"` returns nothing). |
| 34 | Evaluation Harness + Flagship Case | 🟥 CORE (biggest credibility lever) | ✅ Done | `eval/harness.py`, `eval/dataset.py`, `run_eval.py`, fully tested — this and #15 are the two most solid pieces of the project. |
| 35 | Demo Recording | 🟥 CORE | ❌ **Not started** | Non-code deliverable — no video artifact in the repo. Needs its own task, not a code fix. |
| 36 | Submission Package | 🟥 CORE | ❌ **Not started** | No track selection, architecture diagram, or sandbox URL committed anywhere yet. |

---

## Open decisions (D1–D4) — none resolved yet
| # | Decision | Status |
|---|---|---|
| D1 | Which track to submit to (New Slack Agent vs. Agent for Good) | Open |
| D2 | Which anti-spoofing voice model, validated on real clips | Open — voice agent ships, but the specific model choice isn't confirmed/validated per the build map's own ask |
| D3 | Where the judge-facing sandbox is hosted for the duration of judging | Open — README only documents local `ngrok`, not a durable host |
| D4 | Embedding model + vector store for #21 | Open — currently running the "no external model needed for demo" fallback, not the pgvector default |

---

## Priority order for what's left

1. **Fix the DB connection-API bug (debug report #1).** This single fix unblocks #2, #26, and #27 all at once — right now they're only "done" on paper.
2. **Decide on #18** (Confidence-Calibrated Silence): either implement it for real, or stop describing it as shipped in the pitch docs. Cheap either way, but pick one before a judge notices the gap.
3. **Decide on the agents-are-heuristic gap.** If actual LLM calls are in scope before the deadline, this is the biggest remaining engineering lift in the project. If not, the pitch language ("LLM-backed agents cross-examine each other") should be tightened to match reality.
4. **#33 Slack Canvas** — smallest CORE-adjacent gap with zero code yet; low effort if the Bolt/Slack API surface is already familiar from #31.
5. **Resolve D1–D4** — these are decisions, not code, and can be closed out in an hour of discussion; several other tickets' "done" status is contingent on them (e.g., #21, #12).
6. **#35/#36** — schedule last, once the above are stable, since re-recording a demo after a late bug fix is wasted effort.
