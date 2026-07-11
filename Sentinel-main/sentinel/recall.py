"""Temporal Recall — Semantic + RTS fallback (build-map ticket #21).

Two-stage lookup: find near-duplicate past cases to surface prior context.

Stage 1 (Primary): Vector-embedding similarity over stored case fingerprints.
  - Uses a lightweight hash-based bag-of-words embedding (no external model
    needed for demo). Real deployment upgrades to sentence-transformers +
    pgvector; the interface is identical.

Stage 2 (Fallback/Verification): Slack Real-Time Search (RTS) API keyword
  search over the workspace history. Structurally distinct from the BFS
  blast-radius (#19), which is spatial. This is temporal.

Demo beat: "91% similar to a case closed 3 weeks ago as a false positive —
here's why this one differs."
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)


# ── In-memory vector store ─────────────────────────────────────────────────────
# Key: case_id → (embedding vector, metadata dict)
# In production, swap this for pgvector; the call site is identical.

_STORE: dict[str, tuple[list[float], dict]] = {}

# Cap the in-memory store so a long-running process can't leak unboundedly.
# (Production swaps this whole store for pgvector; the cap is a safety net.)
_STORE_MAX = 5000


@dataclass
class RecallMatch:
    """One prior case that is semantically similar to the current one."""

    case_id: str
    similarity: float              # cosine similarity 0..1
    verdict: str
    description: str
    created_at: Optional[datetime] = None
    found_via: str = "embedding"   # "embedding" | "rts"


# ── Embedding ──────────────────────────────────────────────────────────────────

def _embed_claims(claims_dict: dict) -> list[float]:
    """Produce a fixed-length embedding from a claims dict.

    This is a lightweight, dependency-free bag-of-features embedding.
    It captures the numeric signals that the contradiction engine uses.
    Upgrade path: replace with sentence-transformers + pgvector.
    """
    # Normalised feature vector — 8 dimensions
    def _safe(v, default=0.0):
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    visual = _safe(claims_dict.get("visual_total"))
    structured = _safe(claims_dict.get("structured_total"))
    ratio = max(visual, structured) / max(min(visual, structured), 1e-9) if (visual and structured) else 0.0

    return [
        min(ratio / 20.0, 1.0),                          # invoice ratio (normed)
        _safe(claims_dict.get("tone_anomaly")),           # [0,1]
        _safe(claims_dict.get("voice_mismatch")),         # [0,1]
        min(_safe(claims_dict.get("domain_age_days"), 365) / 365.0, 1.0),  # normed age
        1.0 if claims_dict.get("injection_present") else 0.0,
        1.0 if claims_dict.get("policy_violation") else 0.0,
        min(_safe(claims_dict.get("finance_risk", 0.0)), 1.0),
        _safe(claims_dict.get("nlp_urgency", 0.0)),
    ]


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ── Public API ─────────────────────────────────────────────────────────────────

def store_case(
    case_id: str,
    claims_dict: dict,
    verdict: str,
    description: str = "",
    created_at: Optional[datetime] = None,
) -> None:
    """Store a case's embedding for future recall lookups."""
    vec = _embed_claims(claims_dict)
    # Evict the oldest entry (dicts preserve insertion order) once at capacity.
    if case_id not in _STORE and len(_STORE) >= _STORE_MAX:
        _STORE.pop(next(iter(_STORE)))
    _STORE[case_id] = (
        vec,
        {
            "verdict": verdict,
            "description": description,
            "created_at": created_at or datetime.now(timezone.utc),
        },
    )
    log.debug("recall: stored case %s (store size=%d)", case_id[:8], len(_STORE))


def find_similar(
    claims_dict: dict,
    top_k: int = 3,
    min_similarity: float = 0.70,
    exclude_case_id: Optional[str] = None,
) -> list[RecallMatch]:
    """Find the most similar past cases using cosine similarity.

    Returns up to top_k matches with similarity >= min_similarity,
    sorted by similarity descending.
    """
    if not _STORE:
        return []

    query_vec = _embed_claims(claims_dict)
    results: list[RecallMatch] = []

    for cid, (vec, meta) in _STORE.items():
        if cid == exclude_case_id:
            continue
        sim = _cosine(query_vec, vec)
        if sim >= min_similarity:
            results.append(
                RecallMatch(
                    case_id=cid,
                    similarity=round(sim, 4),
                    verdict=meta["verdict"],
                    description=meta["description"],
                    created_at=meta.get("created_at"),
                    found_via="embedding",
                )
            )

    results.sort(key=lambda r: r.similarity, reverse=True)
    return results[:top_k]


# ── Slack RTS fallback ─────────────────────────────────────────────────────────

async def rts_search(
    query: str,
    channel: Optional[str] = None,
    count: int = 5,
) -> list[dict]:
    """Call the Slack Real-Time Search API as a fallback / verification layer.

    Returns a list of raw Slack message dicts matching the query.
    Falls back gracefully if SLACK_BOT_TOKEN is not configured.

    This is RTS use #2 (temporal recall) — structurally distinct from the
    spatial BFS blast-radius (#19). Both are required by the tech story.
    """
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        log.warning("recall: SLACK_BOT_TOKEN not set — RTS search skipped")
        return []

    try:
        import httpx  # type: ignore

        params: dict = {"query": query, "count": count, "highlight": False}
        if channel:
            params["query"] = f"in:{channel} {query}"

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://slack.com/api/search.messages",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            data = resp.json()

        if not data.get("ok"):
            log.warning("recall: RTS error: %s", data.get("error"))
            return []

        matches = data.get("messages", {}).get("matches", [])
        log.info("recall: RTS returned %d matches for query %r", len(matches), query)
        return matches

    except Exception as e:
        log.warning("recall: RTS search failed: %s", e)
        return []


async def recall(
    case_id: str,
    claims_dict: dict,
    verdict: str,
    channel: Optional[str] = None,
    rts_query: Optional[str] = None,
) -> list[RecallMatch]:
    """Full temporal recall: embedding search first, RTS fallback.

    Also stores the current case so future cases can recall it.
    """
    # 1. Embedding search (primary)
    matches = find_similar(claims_dict, exclude_case_id=case_id)

    # 2. RTS fallback — used when embedding store is cold or as verification
    if not matches and rts_query:
        rts_hits = await rts_search(rts_query, channel=channel)
        for hit in rts_hits[:3]:
            matches.append(
                RecallMatch(
                    case_id=hit.get("ts", "unknown"),
                    similarity=0.0,  # RTS doesn't give a similarity score
                    verdict="UNKNOWN",
                    description=hit.get("text", "")[:120],
                    found_via="rts",
                )
            )

    # 3. Store this case for future recall
    store_case(
        case_id=case_id,
        claims_dict=claims_dict,
        verdict=verdict,
        description=f"Case {case_id[:8]} — verdict {verdict}",
    )

    return matches
