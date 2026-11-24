import atexit

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool = None


class DatabaseError(RuntimeError):
    pass


def verify_database_url(database_url):
    try:
        with psycopg.connect(database_url, connect_timeout=5) as conn:
            conn.execute("SELECT 1")
    except psycopg.Error as exc:
        raise DatabaseError(f"Database connection failed: {exc}".strip()) from exc


def init_pool(database_url, min_size=1, max_size=10):
    global _pool
    if _pool is not None:
        return _pool
    verify_database_url(database_url)
    _pool = ConnectionPool(
        database_url,
        min_size=min_size,
        max_size=max_size,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    _pool.open(wait=True, timeout=10)
    atexit.register(close_pool)
    return _pool


def get_pool():
    if _pool is None:
        raise DatabaseError("Database pool has not been initialised")
    return _pool


def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def check_database_connection():
    try:
        with get_pool().connection(timeout=5) as conn:
            return conn.execute(
                "SELECT current_database() AS database, version() AS version"
            ).fetchone()
    except Exception as exc:
        raise DatabaseError(f"Database connection failed: {exc}") from exc
