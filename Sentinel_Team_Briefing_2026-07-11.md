# Sentinel — Team Briefing Before You Go Further
**Prepared:** 2026-07-11 · **Deadline: 2026-07-13, 5:00 PM PDT — that's ~2 days from right now.**

This is everything I'd want a teammate to know before touching the code again. It's organized by urgency, not by how interesting each section is — read §1 and §2 first, the rest can wait until those are handled.

---

## 1. The deadline changes what "further" should mean

`SUBMISSION.md` has the date. You're not in a "keep building features" window anymore — you're in a "make what exists undeniable" window. Concretely, that means:

- **Stop adding new tickets.** Everything in the build map (#1–#36) is marked done. Resist the urge to start a #37.
- **Time budget for the rest of this window should go, in order: (a) confirm the live judge-facing sandbox is actually up and stays up, (b) rehearse the demo script against the real system at least twice, (c) fix anything that breaks during rehearsal, (d) only then, cosmetic polish.**
- The submission checklist (`SUBMISSION.md` §36) needs a **live Slack sandbox URL that stays up through judging** (decision D3: Render/Railway + Vercel). I have no way to check from here whether that's actually deployed and warm right now — that's the single highest-priority thing to verify today, not tomorrow, because DNS/hosting problems are exactly the kind of thing that surfaces at the worst time.

---

## 2. What I fixed this week (recap, so everyone's on the same page)

Three bugs meant **neither documented way to run the project worked out of the box**:

1. `pyproject.toml` was missing package-discovery config → `pip install -e .` hard-failed → **the Docker build in your own `docker compose up` Quickstart never completed.**
2. The in-memory (no-Postgres) backend had drifted out of sync with the real one — missing the `amount_at_risk` field entirely — so the React console's "start investigation" button 500'd every time in that mode, and the case list silently ate the error and showed nothing.
3. `pytest.ini` and `pyproject.toml` both configured pytest, and the wrong one won — `pytest tests/ -v`, exactly as your README tells people to run it, failed 2 tests every time with no real Postgres running.

All three are fixed and re-verified: Docker build installs clean, the console investigate flow works end-to-end in-memory, and the suite runs in 1.8s at 244 passed / 5 correctly skipped (down from 212s with false failures). I also deleted dead scaffold weight from the frontend (`@google/genai`, `express`, `dotenv` and friends — leftover from the AI Studio template, zero references anywhere in `src/`) and fixed the frontend's `.env.example`, which was documenting an irrelevant `GEMINI_API_KEY` while never mentioning the `VITE_API_URL` the app actually needs.

**What this means for the team:** the code you're sitting on right now is more trustworthy than what existed a few days ago, but it got there by fixing things nobody had exercised end-to-end. Take that as a signal, not just a relief — see §4.

---

## 3. The honesty audit: what's real, what's deterministic, what's simulated

This matters because your own demo script (§35 in `SUBMISSION.md`) already commits to "radical candor — name what's simulated (federation, honeypot) on camera." Good instinct. But going through the code, the honest inventory is a bit bigger than those two. Better you hear it from me now than from a judge's question live.

| Component | What it actually is | Judge-facing risk |
|---|---|---|
| Contradiction engine (#15) | Real. Deterministic symbolic reconciler, genuinely the strongest and most defensible piece. | Low — this is your best story, lead with it. |
| Finance / NLP / Vision / Threat-Intel agents (#7–#10) | **Not LLM-backed at all.** Finance agent's own docstring: *"No LLM. No XGBoost. Just deterministic finance math."* NLP agent: *"No LLM — pure pattern matching."* Vision agent does real PDF text extraction (pdfminer) + regex, not a vision model. Threat-intel does real VirusTotal/WHOIS lookups when a key is set, else serves from a seeded cache. | **Medium.** The pitch language ("specialist agents," "cross-examine") reads as LLM-agent framing to anyone not in the code. It's a *defensible* engineering choice — deterministic means reliable on stage, testable, no API-key dependency, no hallucination risk — but if a judge asks "which model powers your vision agent" and the honest answer is "none, it's regex + pdfminer," you want that answer rehearsed and confident, not fumbled. I'd frame it proactively as a *design decision* ("we chose deterministic extraction over LLM calls for demo reliability and testability — happy to talk about the tradeoff") rather than waiting to be caught. |
| Voice authenticity agent (#12) | Real acoustic feature detector, but trained/validated on **one curated real-vs-cloned clip pair**, not a general dataset. `SUBMISSION.md` itself is candid about this ("AUC=1.0 on the curated pair... don't claim a pretrained SOTA model you didn't train"). | Medium — AUC=1.0 on n=1 pair is a real signal for that specific demo clip, not a generalization claim. Don't let a teammate accidentally say "our model has perfect accuracy" out loud without the qualifier. |
| Compliance agent (#13) | Real logic, but running over "a curated lookup over a hand-written excerpt" of compliance rules, not a full regulatory database. | Low-medium, same pattern — fine if framed as a demo-scoped excerpt. |
| Federated pattern network (#29) | Fully simulated (`simulated: bool = True # ALWAYS True for hackathon`). | **Already on your disclosure list.** Good. |
| Honeypot agent (#25) | Scripted exchange in a sandboxed thread, explicitly never run against a real attacker. | **Already on your disclosure list.** Good. |
| Red-team / adversarial self-play (#16–#17) | Worth double-checking before demo day — I didn't do a deep pass on these two specifically; flagging as unverified rather than either "fine" or "risky." | Unknown — verify before you rely on it live. |

None of this means the project is weaker than it looks — a deterministic, testable pipeline that never hallucinates is a legitimately good pitch to a technical judge, arguably a *better* engineering story than "we called GPT-4 eight times." The risk isn't the choice, it's being asked about it and not having the answer ready.

---

## 4. The bug pattern itself is a signal, not just three bugs

All three fixes in §2 came from the same root cause: **the in-memory backend and the Postgres backend were allowed to drift apart, and nobody had a way to notice.** Every time a new field got added to the real schema (`amount_at_risk` via migration 003), the in-memory stub silently fell behind, because there's no test that runs the same assertions against both backends.

You don't have time to fix this properly before the deadline, and you shouldn't try. But it's worth the team knowing *why* it happened, because it'll happen again with the next field you add if someone touches `repo.py` without touching `repo_memory.py` in the same commit. If anyone on the team adds a new case field between now and submission, grep for it in `repo_memory.py` in the same sitting — don't wait for a test to catch it, because right now nothing does automatically.

---

## 5. Test suite / demo readiness — what's actually confirmed vs. what I couldn't check

**Confirmed working, by me, live, in this pass:**
- `pip install -e .` and the full Docker packaging path
- Full pytest suite (244 passed, 3.18s → 1.8s after config fix)
- In-memory console path: `POST /api/investigate` → case created → shows up in `GET /cases`
- `python -m sentinel.make_fixtures` (your documented pre-demo setup step 1) — runs clean, regenerates all four demo artifacts including the AUC=1.0 voice pair
- Frontend: clean `tsc --noEmit`, clean `vite build`, identical bundle output after removing dead dependencies
- Every `.py` file in the repo byte-compiles with no syntax errors; every core module (`gateway`, `worker`, `slack_app`, `sse_worker`, both DB backends, rules engine, eval harness) imports cleanly

**Not confirmed, because I have no way to from here:**
- The actual live Slack round-trip (`@Sentinel investigate` in a real workspace → posted verdict card). I traced the code path (`slack_app.on_mention` → `worker.investigate` → Block Kit post) and it reads correctly, but "reads correctly" isn't the same guarantee as "watched it work." **Someone on the team needs to run this for real, today or tomorrow, not assume it from a code read.**
- Whether the Render/Railway + Vercel sandbox (decision D3) is actually deployed and warm right now.
- Red-team / adversarial self-play agents (§3, noted above).
- The 3:00 demo script's actual timing against the real system — rehearse it with a stopwatch at least once before judging.

---

## 6. Prioritized action list for the next 2 days

**Today:**
1. Confirm the judge-facing sandbox (Slack workspace + hosted backend + console) is live and reachable by someone outside the team, on a different network.
2. Run the actual Slack flow once, live, in the real workspace — not the in-memory console. If it's broken, you want to know today, not during judging.
3. Rehearse the 3-minute demo script end to end, with a stopwatch, against the real deployed stack.

**Tomorrow:**
4. Fix whatever rehearsal surfaces. Nothing else.
5. Record the 3:00 demo video, submit early rather than at the deadline — leave buffer for upload/processing issues.
6. Have one person specifically prep answers for "which model powers X agent" and "what's simulated" — not just the two items already on your disclosure list, the fuller inventory in §3.

**Don't do:**
- Don't start new tickets.
- Don't refactor the DB layer drift issue in §4 properly — patch-level fixes only if something breaks, no redesign this close to the deadline.
- Don't let bundle-size warnings, remaining frontend cosmetics, or anything not on the above list eat time before judging.

---

## 7. Bottom line

Technically, this is a stronger-than-average hackathon submission — the contradiction engine is a real differentiator, the system design (audit chain, SSE, dual-backend, eval harness) shows genuine depth, and it's now actually runnable end-to-end, which per the bugs found here, isn't guaranteed for every team walking in. The remaining risk isn't code quality at this point — it's operational (is the live sandbox actually up) and narrative (is the team ready to talk honestly about which parts are LLM-free-by-design vs. genuinely simulated). Both of those are solvable in the next two days without writing another line of feature code.
