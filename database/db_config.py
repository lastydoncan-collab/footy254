"""
PostgreSQL access for FOOTY254.

``get_connection()`` is the single entry point used by every repository. It
returns a *pooled* connection: ``close()`` (or leaving a ``with`` block) hands
the connection back to the pool instead of tearing down a TCP + auth session,
which is by far the biggest per-request latency cost of the original
"connect on every query" design.

The returned object behaves like a psycopg2 connection, so repositories need no
changes. Safety nets against leaks:

* leaving a ``with get_connection() as conn:`` block commits/rolls back and
  returns the connection;
* a connection that is garbage-collected without being closed is returned too;
* waiting for a free connection blocks (up to ``DB_POOL_WAIT_SECONDS``) rather
  than failing instantly when the pool is momentarily busy.

Set ``DB_POOL_ENABLED=false`` to fall back to plain unpooled connections.
"""

import logging
import os
import threading
import time

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor

from config import settings

logger = logging.getLogger(__name__)

# A pooled connection idle for longer than this is probed before reuse, because
# proxies / managed databases silently drop idle TCP sessions.
_STALE_AFTER_SECONDS = 30


# ==========================================================
# CONNECTION PARAMETERS
# ==========================================================

def _connect_kwargs() -> dict:
    password = os.getenv("FOOTY254_DB_PASSWORD")

    if not password:
        raise RuntimeError(
            "FOOTY254_DB_PASSWORD is not set. Set it in your .env file "
            "(see .env.example) before starting the backend."
        )

    return {
        "dbname": os.getenv("FOOTY254_DB_NAME", "footy254"),
        "user": os.getenv("FOOTY254_DB_USER", "postgres"),
        "password": password,
        "host": os.getenv("FOOTY254_DB_HOST", "localhost"),
        "port": os.getenv("FOOTY254_DB_PORT", "5432"),
        "sslmode": os.getenv("FOOTY254_DB_SSLMODE", "prefer"),
        "connect_timeout": settings.DB_CONNECT_TIMEOUT,
        "application_name": "footy254",
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
        "cursor_factory": RealDictCursor,
    }


def get_raw_connection():
    """An unpooled, caller-owned connection (migrations, advisory locks)."""

    return psycopg2.connect(**_connect_kwargs())


# ==========================================================
# POOL
# ==========================================================

_pool = None
_pool_lock = threading.Lock()
_slots = None  # bounds concurrent checkouts so callers wait instead of failing
_last_used: dict[int, float] = {}


def _get_pool():
    global _pool, _slots

    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _slots = threading.BoundedSemaphore(settings.DB_POOL_MAX)
                _pool = pg_pool.ThreadedConnectionPool(
                    1,
                    settings.DB_POOL_MAX,
                    **_connect_kwargs(),
                )
                logger.info(
                    "Database pool ready (max %d connections).",
                    settings.DB_POOL_MAX,
                )

    return _pool


def close_pool() -> None:
    """Close every pooled connection (application shutdown)."""

    global _pool

    with _pool_lock:
        if _pool is not None:
            try:
                _pool.closeall()
            finally:
                _pool = None
                _last_used.clear()


class PooledConnection:
    """Thin proxy that returns its connection to the pool on ``close()``."""

    def __init__(self, conn, owner_pool, slots):
        self._conn = conn
        self._pool = owner_pool
        self._slots = slots
        self._released = False

    # psycopg2 API surface used by the repositories -------------------------

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def __getattr__(self, name):
        # Anything else (autocommit, closed, set_session, ...) is delegated.
        # Private names are never delegated: this also prevents infinite
        # recursion if __init__ failed before ``_conn`` was assigned.
        if name.startswith("_"):
            raise AttributeError(name)

        return getattr(self._conn, name)

    def __setattr__(self, name, value):
        if name in {"_conn", "_pool", "_slots", "_released"}:
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn, name, value)

    # Lifecycle -------------------------------------------------------------

    def close(self):
        if self._released:
            return

        self._released = True
        conn = self._conn

        try:
            if conn.closed:
                self._pool.putconn(conn, close=True)
            else:
                try:
                    conn.rollback()  # never hand back an open transaction
                    _last_used[id(conn)] = time.monotonic()
                    self._pool.putconn(conn)
                except Exception:
                    self._pool.putconn(conn, close=True)
        except Exception:
            logger.exception("Failed returning a connection to the pool.")
        finally:
            self._slots.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self.close()

        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def _checkout():
    owner_pool = _get_pool()

    if not _slots.acquire(timeout=settings.DB_POOL_WAIT_SECONDS):
        raise RuntimeError("Database is busy. Please try again shortly.")

    try:
        conn = owner_pool.getconn()

        idle = time.monotonic() - _last_used.get(id(conn), time.monotonic())

        if conn.closed or idle > _STALE_AFTER_SECONDS:
            alive = False

            if not conn.closed:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                    conn.rollback()
                    alive = True
                except Exception:
                    alive = False

            if not alive:
                owner_pool.putconn(conn, close=True)
                conn = owner_pool.getconn()

        return PooledConnection(conn, owner_pool, _slots)
    except Exception:
        _slots.release()
        raise


def get_connection():
    if not settings.DB_POOL_ENABLED:
        return get_raw_connection()

    return _checkout()


def get_cursor():
    conn = get_connection()
    return conn.cursor()


def check_database() -> bool:
    """Cheap liveness probe used by the readiness endpoint."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            cur.fetchone()

    return True
