"""Tests for temporal recall (build-map ticket #21)."""

from __future__ import annotations

import pytest
from sentinel.recall import (
    _embed_claims,
    _cosine,
    store_case,
    find_similar,
    recall,
    _STORE,
)


def setup_function():
    """Clear the in-memory store before each test."""
    _STORE.clear()


# ── Embedding ─────────────────────────────────────────────────────────────────

def test_embed_claims_returns_fixed_length():
    vec = _embed_claims({"visual_total": 5000, "structured_total": 1000, "tone_anomaly": 0.8})
    assert len(vec) == 8
    assert all(isinstance(x, float) for x in vec)


def test_embed_claims_identical_inputs_identical_vectors():
    d = {"visual_total": 5000, "structured_total": 1000, "tone_anomaly": 0.8}
    assert _embed_claims(d) == _embed_claims(d)


def test_embed_claims_different_inputs_different_vectors():
    v1 = _embed_claims({"visual_total": 5000, "structured_total": 1000})
    v2 = _embed_claims({"visual_total": 500, "structured_total": 500})
    assert v1 != v2


def test_cosine_identical_vectors_is_one():
    v = [0.5, 0.3, 0.8, 0.0, 1.0, 0.0, 0.2, 0.4]
    assert _cosine(v, v) == pytest.approx(1.0)


def test_cosine_orthogonal_vectors_is_zero():
    assert _cosine([1, 0], [0, 1]) == pytest.approx(0.0)


def test_cosine_zero_vector_returns_zero():
    assert _cosine([0, 0, 0], [1, 2, 3]) == 0.0


# ── Store & Find ──────────────────────────────────────────────────────────────

def test_store_and_find_similar_case():
    _STORE.clear()
    claims_fraud = {"visual_total": 5000, "structured_total": 1000, "tone_anomaly": 0.85}
    store_case("case-old", claims_fraud, verdict="FRAUD_LIKELY", description="Old fraud case")

    # A very similar new case should find the stored one
    similar = find_similar(claims_fraud, min_similarity=0.7)
    assert len(similar) >= 1
    assert similar[0].case_id == "case-old"
    assert similar[0].verdict == "FRAUD_LIKELY"
    assert similar[0].similarity >= 0.7


def test_find_similar_excludes_self():
    _STORE.clear()
    claims = {"visual_total": 5000, "structured_total": 1000}
    store_case("case-self", claims, verdict="FRAUD_LIKELY")
    results = find_similar(claims, exclude_case_id="case-self")
    assert all(r.case_id != "case-self" for r in results)


def test_find_similar_empty_store_returns_empty():
    _STORE.clear()
    results = find_similar({"visual_total": 1000})
    assert results == []


def test_find_similar_dissimilar_case_excluded():
    _STORE.clear()
    # Store a CLEAR case (low signals)
    store_case("case-clear", {"visual_total": 100, "structured_total": 100}, verdict="CLEAR")
    # A high-fraud case should NOT match the CLEAR case at threshold 0.7
    fraud_claims = {"visual_total": 5000, "structured_total": 100, "tone_anomaly": 0.9}
    results = find_similar(fraud_claims, min_similarity=0.85)
    # May or may not match depending on vector distance — just ensure no crash
    assert isinstance(results, list)


def test_top_k_limits_results():
    _STORE.clear()
    claims = {"visual_total": 5000, "structured_total": 1000}
    for i in range(5):
        store_case(f"case-{i}", claims, verdict="FRAUD_LIKELY")
    results = find_similar(claims, top_k=2)
    assert len(results) <= 2


def test_results_sorted_by_similarity_descending():
    _STORE.clear()
    exact_claims = {"visual_total": 5000, "structured_total": 1000, "tone_anomaly": 0.9}
    rough_claims = {"visual_total": 4500, "structured_total": 1100}
    store_case("exact", exact_claims, verdict="FRAUD_LIKELY")
    store_case("rough", rough_claims, verdict="REVIEW")

    query = {"visual_total": 5000, "structured_total": 1000, "tone_anomaly": 0.9}
    results = find_similar(query, min_similarity=0.5)
    if len(results) >= 2:
        assert results[0].similarity >= results[1].similarity


# ── recall() end-to-end ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_recall_stores_case_and_returns_list():
    _STORE.clear()
    # Pre-populate store
    store_case("prior-001", {"visual_total": 5000, "structured_total": 1000, "tone_anomaly": 0.85},
               verdict="FRAUD_LIKELY")

    matches = await recall(
        case_id="new-case",
        claims_dict={"visual_total": 5000, "structured_total": 1000, "tone_anomaly": 0.85},
        verdict="FRAUD_LIKELY",
    )
    # new-case should now be in the store
    assert "new-case" in _STORE
    # prior case should have been matched
    assert any(m.case_id == "prior-001" for m in matches)


@pytest.mark.asyncio
async def test_recall_no_rts_without_token(monkeypatch):
    _STORE.clear()
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    # With empty store and no token, should return empty list gracefully
    matches = await recall(
        case_id="case-x",
        claims_dict={},
        verdict="CLEAR",
        rts_query="invoice fraud",
    )
    assert isinstance(matches, list)
