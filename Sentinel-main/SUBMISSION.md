# Sentinel — Submission Playbook (#35 / #36 / decisions)

This is the non-code checklist to actually ship. Everything in code is done and
tested; this file is the human runbook. **Deadline: 2026-07-13 5:00 PM PDT.**

---

## Decisions (recommended answers to #D1–#D4)

| # | Decision | Recommendation | Why |
|---|---|---|---|
| **D1** | Track: "New Slack Agent" vs "Agent for Good" | **New Slack Agent** | The BFS blast-radius + MCP history retrieval + RTS make Slack the compute engine — the platform-alignment story scores 10/10 there. |
| **D2** | Voice model | **Ship the hybrid** (acoustic detector, AUC=1.0 on the curated pair) + lead with **Linguistic-Acoustic Mismatch** (Appendix A.7). Don't claim a pretrained SOTA model you didn't train. | Defensible under questioning; the curated-pair AUC is honest. |
| **D3** | Judge sandbox hosting | **Render/Railway free tier** for the FastAPI+Postgres, **Vercel** for the React console. Keep it warm on demo day. | Judges need a live Slack workspace URL that stays up. |
| **D4** | Embedding / vector store | Keep the in-memory bag-of-features for the demo; note **pgvector + sentence-transformers** as the one-line prod upgrade. | The interface is identical; don't add infra risk before the deadline. |

---

## Pre-demo setup (run once)

```bash
# 1. Generate curated artifacts (XOR PDF, injection invoice, real/cloned voice)
python -m sentinel.make_fixtures        # -> ./demo_artifacts/

# 2. Bring up the stack (fresh volume auto-applies all migrations)
docker compose down -v && docker compose up -d

# 3. Confirm the pipeline (green suite)
python -m pytest tests/ -q
```

---

## #35 — 3:00 demo script (cold open -> self-improving close)

1. **0:00 Cold open** — play the cloned CEO voicemail. "This voice ordered a
   $5M wire. It's fake. Sentinel is the only thing that noticed."
2. **0:20 Trigger** — in Slack, forward the invoice + type `@Sentinel investigate`.
   ACK card appears in <5ms.
3. **0:35 Agents fan out** — React console lights up 8 agents live via SSE.
4. **0:55 File forensics** — the `file_forensics` beat surfaces the XOR payload
   hidden after `%%EOF` (real, from `hidden_payload_invoice.pdf`).
5. **1:10 MCP baseline** — `mcp_baseline` event: "pulled the CEO's writing
   history to fingerprint tone." Then `voice_analysis`: anti-spoof score + AUC.
6. **1:30 Contradiction engine** — 3 axes fire (visual/structured, tone, voice).
   **Click a contradiction axis** -> jumps to the source cell/bbox/token.
7. **1:55 Verdict** — FRAUD_LIKELY, expected-loss $ headline, blast radius map.
8. **2:15 Self-writing rule** — a shadow rule is drafted from this case.
9. **2:30 The closing loop** — run a *second* case that trips the rule from case
   #1 and resolves instantly. "It just learned, live."
10. **2:50 Radical candor** — name what's simulated (federation, honeypot) on
    camera. Judges reward the honesty.

---

## #36 — Devpost submission checklist

- [ ] Devpost project created, track = **New Slack Agent** (D1)
- [ ] 3:00 video uploaded (unlisted YouTube/Vimeo link)
- [ ] **Live Slack sandbox URL** that stays up through judging (D3)
- [ ] Architecture diagram (reuse the mermaid in Master Reference §A.8)
- [ ] Repo link + README quickstart verified on a clean clone
- [ ] Add judges to the Slack workspace: `slackhack@salesforce.com`,
      `testing@devpost.com`
- [ ] Text writeup: lead with the 3-way contradiction engine + honest scoping
- [ ] List tech: Slack (Events API, MCP, RTS, Block Kit, Canvas), FastAPI,
      Postgres, deterministic reconciler

---

## Known issue to fix before recording

- **Frontend build:** `App.tsx:185` passes an `investigation` prop that
  `DashboardConsoleProps` doesn't declare — `tsc` fails (pre-existing, not from
  the agent fixes). `npm run dev` (Vite/esbuild) still serves, but `npm run
  build` will fail. Reconcile `DashboardConsole` vs `LiveInvestigation` props
  before relying on a production build.
