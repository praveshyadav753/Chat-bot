from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from dotenv import load_dotenv
import os

load_dotenv()

db_url = os.getenv("DATABASE_URL1")

_checkpointer: AsyncPostgresSaver | None = None
_pool: AsyncConnectionPool | None = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """
    Returns a module-level AsyncPostgresSaver backed by a connection pool.
    Safe for concurrent async requests — each checkout gets its own connection.
    Call once at app startup or lazily on first request.
    """
    global _checkpointer, _pool

    if _checkpointer is not None:
        return _checkpointer

    setup_pool = AsyncConnectionPool(
        conninfo=db_url,
        kwargs={"autocommit": True},
        min_size=1,
        max_size=2,
        open=False,
    )
    await setup_pool.open()
    try:
        setup_saver = AsyncPostgresSaver(setup_pool)
        await setup_saver.setup()
    finally:
        await setup_pool.close()

    pool = AsyncConnectionPool(
        conninfo=db_url,
        min_size=2,
        max_size=10,
        open=False,
    )
    await pool.open()
    _pool = pool

    _checkpointer = AsyncPostgresSaver(pool)

    return _checkpointer


async def close_checkpointer() -> None:
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
        _pool = None
        _checkpointer = None
