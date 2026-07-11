"""Idempotent startup migration runner.

Every migration in sentinel/db/migrations/ is written to be safe to run
repeatedly (CREATE TABLE IF NOT EXISTS, ADD COLUMN IF NOT EXISTS, DROP
CONSTRAINT IF EXISTS + ADD). Running them all in filename order on startup means
an existing Postgres volume gets migrations 002/003 without any manual psql —
the docker-entrypoint only auto-applies them on a *fresh* volume.

Called from the FastAPI lifespan (gateway.py) right after the pool opens.
No-ops cleanly in memory:// mode.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def run_migrations() -> None:
    """Apply every *.sql migration in filename order. Idempotent; fails soft."""
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn or dsn == "memory://":
        log.info("migrate: memory:// mode — skipping SQL migrations")
        return

    from .pool import get_db_pool

    files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        return

    pool = await get_db_pool()
    async with pool.connection() as conn:
        for f in files:
            sql = f.read_text(encoding="utf-8")
            try:
                await conn.execute(sql)
                log.info("migrate: applied %s", f.name)
            except Exception as e:
                # Idempotent DDL should not fail, but never let a migration
                # abort startup — log and continue so the service still boots.
                log.warning("migrate: %s raised (continuing): %s", f.name, e)
