"""Gateway endpoint tests — real pipeline, no mocks.

conftest.py sets the env vars (SLACK_BOT_TOKEN etc.) before this module
is imported, so all sentinel modules load cleanly.

Two tiers of tests:
  - No marker  →  run without Docker (TestClient without lifespan, so the
                   DB pool is never opened). Safe for CI with no database.
  - @pytest.mark.integration  →  require `docker compose up -d` first.
                   These open the real DB pool and hit real Postgres.
"""

import pytest
from starlette.testclient import TestClient

# conftest.py has already set the env vars — safe to import sentinel now
from sentinel.gateway import api


# ── Tier 1: no DB needed (TestClient without context manager = no lifespan) ───

def test_health_endpoint():
    """GET /health returns 200 without needing a DB connection."""
    client = TestClient(app=api, raise_server_exceptions=True)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "sentinel-gateway"
    assert "version" in data


def test_graph_snapshot_empty():
    """GET /graph/snapshot returns a valid JSON structure even when the graph is empty."""
    import networkx as nx
    from sentinel.graph import cache as _cache_mod
    _cache_mod._graph = nx.DiGraph()  # reset to known state

    client = TestClient(app=api, raise_server_exceptions=True)
    resp = client.get("/graph/snapshot")

    assert resp.status_code == 200
    data = resp.json()
    assert data["node_count"] == 0
    assert data["edge_count"] == 0
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)


def test_graph_snapshot_after_ingest():
    """GET /graph/snapshot reflects events already in the in-memory graph."""
    import asyncio
    import networkx as nx
    from sentinel.graph import cache as _cache_mod

    _cache_mod._graph = nx.DiGraph()
    asyncio.run(_cache_mod.ingest_event(
        {"type": "message", "user": "U999", "channel": "C001", "ts": "1.0"}
    ))

    client = TestClient(app=api, raise_server_exceptions=True)
    resp = client.get("/graph/snapshot")

    assert resp.status_code == 200
    data = resp.json()
    assert data["node_count"] == 2   # U999 + C001
    assert data["edge_count"] == 1


# ── Tier 2: integration — require `docker compose up -d` ─────────────────────

@pytest.mark.integration
def test_get_case_404_real_db():
    """GET /cases/{id} returns 404 for a non-existent case (real Postgres)."""
    with TestClient(app=api) as client:          # context manager → lifespan runs → DB pool opens
        resp = client.get("/cases/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.integration
def test_audit_verify_empty_chain():
    """GET /audit/verify returns intact=True on an empty chain (real Postgres)."""
    with TestClient(app=api) as client:
        resp = client.get("/audit/verify")
    assert resp.status_code == 200
    data = resp.json()
    assert data["intact"] is True
