"""
database.py — Postgres connection pool (singleton)

How it works:
    - We create ONE pool for the entire bot lifetime
    - The pool keeps a few connections open and ready (min_size)
    - When your code needs the DB, it borrows a connection, uses it, returns it
    - You never open/close connections manually — the pool handles it

Usage:
    from src.core.database import init_db, close_db, pool

    # In your main():
    await init_db()       # opens the pool + enables pgvector
    ...
    await close_db()      # closes everything cleanly on shutdown

    # How to run a query:
    async with pool.connection() as conn:
        await conn.execute("INSERT INTO messages ...")
"""

import asyncio
import os
import logging
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

# Build the connection string
conninfo = (
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST', 'unit-01.infra.orb.local')}:{os.getenv('POSTGRES_PORT', '5432')}"
    f"/{os.getenv('POSTGRES_DB')}"
)

# The global pool — one instance for the whole bot
# The pool won't try to connect at import time
pool = AsyncConnectionPool(
    conninfo,
    min_size=2,  # 2 connections always ready
    max_size=5,  # increase when scaling is needed
    open=False,
)

CLOSE_DB_TIMEOUT = 30
_DB_CONNECT_RETRIES = 10
_DB_CONNECT_DELAY = 3  # seconds between attempts


async def init_db() -> None:
    """Call once at bot startup to open the pool and setup extensions.

    Retries up to _DB_CONNECT_RETRIES times with a fixed delay to handle
    the case where Postgres is still starting when the bot container comes up.

    Raises:
        Exception: Re-raises the last connection error once retries are exhausted.
    """
    last_error: Exception | None = None
    for attempt in range(1, _DB_CONNECT_RETRIES + 1):
        try:
            await pool.open(wait=True)
            async with pool.connection() as conn:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            logger.info("Database pool is ready.")
            return
        except Exception as e:
            last_error = e
            logger.warning(
                "Database not ready (attempt %d/%d): %s. Retrying in %ds...",
                attempt,
                _DB_CONNECT_RETRIES,
                e,
                _DB_CONNECT_DELAY,
            )
            await asyncio.sleep(_DB_CONNECT_DELAY)

    raise last_error  # type: ignore[misc]


async def close_db() -> None:
    if pool.closed:
        logging.info("Database pool already closed.")
        return
    await pool.close(timeout=CLOSE_DB_TIMEOUT)
    logger.info("Database pool is closed.")
