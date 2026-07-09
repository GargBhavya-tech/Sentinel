"""Connection pool singleton for async psycopg3.

The pool is created once at FastAPI startup via the lifespan context manager
in gateway.py and torn down on shutdown. A module-level `_pool` variable
holds the singleton; every repo call acquires a connection from it.
"""

from __future__ import annotations

import os
from typing import Optional

import psycopg_pool  # type: ignore

_pool: Optional[psycopg_pool.AsyncConnectionPool] = None


async def get_db_pool() -> psycopg_pool.AsyncConnectionPool:
    """Return (or lazily create) the shared async connection pool."""
    global _pool
    if _pool is None:
        dsn = os.environ["DATABASE_URL"]
        _pool = psycopg_pool.AsyncConnectionPool(
            conninfo=dsn,
            min_size=2,
            max_size=10,
            open=False,
        )
        await _pool.open()
    return _pool


async def close_db_pool() -> None:
    """Gracefully close the pool — called during FastAPI shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
