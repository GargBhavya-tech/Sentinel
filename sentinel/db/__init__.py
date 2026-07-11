"""Database package — auto-selects backend based on DATABASE_URL env var.

When DATABASE_URL=memory:// (local dev without PostgreSQL):
  → Uses in-memory stubs from repo_memory.py
  → All repo functions work identically; data lives in Python dicts

When DATABASE_URL=postgresql://... (Docker / production):
  → Uses real psycopg3 async pool from pool.py and repo.py

Usage:
    from sentinel.db import get_db_pool, close_db_pool, repo
    await get_db_pool()
    case = await repo.create_case(...)
"""

import os

_DATABASE_URL = os.environ.get("DATABASE_URL", "")

if _DATABASE_URL == "memory://" or not _DATABASE_URL:
    # In-memory mode — no PostgreSQL required
    from .repo_memory import get_db_pool, close_db_pool
    from . import repo_memory as repo
else:
    # Real PostgreSQL mode
    from .pool import get_db_pool, close_db_pool
    from . import repo


__all__ = ["get_db_pool", "close_db_pool", "repo"]
