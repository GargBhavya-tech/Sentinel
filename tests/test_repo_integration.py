"""Integration tests that exercise the REAL psycopg3 path against a live
Postgres — the exact surface the in-memory repo fakes hid.

These are skipped automatically when no database is reachable (e.g. local runs
without `docker compose up`), so the default suite stays hermetic. In CI/Docker,
set DATABASE_URL and they run.

Run explicitly:  pytest -m integration -v
"""

from __future__ import annotations

import os

import pytest

from sentinel.db import repo
from sentinel.db.pool import get_db_pool, close_db_pool

pytestmark = pytest.mark.integration


async def _db_available() -> bool:
    """True if we can actually open the pool + run a trivial query."""
    if not os.environ.get("DATABASE_URL"):
        return False
    try:
        pool = await get_db_pool()
        async with pool.connection() as c:
            await c.execute("SELECT 1")
        return True
    except Exception:
        return False


@pytest.fixture(autouse=True)
async def _skip_without_db():
    if not await _db_available():
        pytest.skip("no reachable Postgres (set DATABASE_URL / docker compose up)")
    yield
    await close_db_pool()


async def test_case_roundtrip_real_db():
    """create_case -> get_case must round-trip through real SQL."""
    case = await repo.create_case(
        slack_channel="C_ITEST",
        slack_ts="1720000000.0001",
        reporter_slack_id="U_ITEST",
    )
    fetched = await repo.get_case(case.case_id)
    assert fetched is not None
    assert fetched.case_id == case.case_id
    assert fetched.reporter_slack_id == "U_ITEST"


async def test_audit_chain_intact_after_appends():
    """Appending several entries must leave verify_audit_chain() intact."""
    case = await repo.create_case("C_ITEST", "1720000000.1", "U_ITEST")
    for i in range(3):
        await repo.append_audit_event(
            case_id=case.case_id,
            event_type="probe",
            payload={"i": i},
        )
    ok, msg = await repo.verify_audit_chain()
    assert ok, f"audit chain reported tampered: {msg}"


async def test_concurrent_audit_appends_do_not_fork_chain():
    """Regression for the advisory-lock fix: many concurrent appends must NOT
    fork the hash chain (which would make verify() fail)."""
    import asyncio

    case = await repo.create_case("C_ITEST", "1720000000.2", "U_ITEST")
    await asyncio.gather(
        *[
            repo.append_audit_event(
                case_id=case.case_id, event_type="concurrent", payload={"n": n}
            )
            for n in range(25)
        ]
    )
    ok, msg = await repo.verify_audit_chain()
    assert ok, f"concurrent appends forked the chain: {msg}"
