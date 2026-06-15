"""SQLite database connection management.

Uses the standard library ``sqlite3`` module wrapped with ``asyncio`` so
the rest of the application can use ``async``/``await`` consistently
without bringing in SQLAlchemy or any other ORM.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "maintenance.db"


def _get_connection() -> sqlite3.Connection:
    """Create a new SQLite connection with sensible defaults."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    return conn


class Database:
    """Thin async wrapper around a single shared sqlite3 connection.

    SQLite connections are not safe to share across threads when used
    directly, so every blocking call is dispatched to a worker thread via
    ``asyncio.to_thread`` and serialized using an ``asyncio.Lock`` to avoid
    "database is locked" errors under concurrent access.
    """

    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()

    def connect(self) -> None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._conn = _get_connection()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database connection has not been initialized")
        return self._conn

    def _execute(self, query: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        cursor = self.connection.cursor()
        cursor.execute(query, tuple(params))
        return cursor

    def _executemany(self, query: str, seq_of_params: Iterable[Iterable[Any]]) -> sqlite3.Cursor:
        cursor = self.connection.cursor()
        cursor.executemany(query, [tuple(p) for p in seq_of_params])
        return cursor

    async def execute(self, query: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        async with self._lock:
            return await asyncio.to_thread(self._execute, query, params)

    async def executemany(self, query: str, seq_of_params: Iterable[Iterable[Any]]) -> sqlite3.Cursor:
        async with self._lock:
            return await asyncio.to_thread(self._executemany, query, seq_of_params)

    async def executescript(self, script: str) -> None:
        async with self._lock:
            await asyncio.to_thread(self.connection.executescript, script)
            await asyncio.to_thread(self.connection.commit)

    async def commit(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self.connection.commit)

    async def fetch_one(self, query: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        async with self._lock:
            cursor = await asyncio.to_thread(self._execute, query, params)
            return await asyncio.to_thread(cursor.fetchone)

    async def fetch_all(self, query: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        async with self._lock:
            cursor = await asyncio.to_thread(self._execute, query, params)
            return await asyncio.to_thread(cursor.fetchall)

    async def execute_and_commit(self, query: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        async with self._lock:
            cursor = await asyncio.to_thread(self._execute, query, params)
            await asyncio.to_thread(self.connection.commit)
            return cursor

    async def executemany_and_commit(
        self, query: str, seq_of_params: Iterable[Iterable[Any]]
    ) -> sqlite3.Cursor:
        async with self._lock:
            cursor = await asyncio.to_thread(self._executemany, query, seq_of_params)
            await asyncio.to_thread(self.connection.commit)
            return cursor


# Single shared instance used across the application.
db = Database()
