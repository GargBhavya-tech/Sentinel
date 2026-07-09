"""Database package — async PostgreSQL via psycopg3.

Usage
-----
    from sentinel.db import get_db_pool, close_db_pool

Call `await get_db_pool()` once at FastAPI startup to create the connection
pool; call `await close_db_pool()` on shutdown. Every repo function accepts
an optional `conn` argument — if omitted it acquires one from the pool.
"""

from .pool import get_db_pool, close_db_pool

__all__ = ["get_db_pool", "close_db_pool"]
