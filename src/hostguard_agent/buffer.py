"""Local durable buffer for outbound telemetry batches.

Batches are stored in SQLite and shipped FIFO with bounded exponential
backoff on failure:

* Idempotent by ``batch_id`` -- re-enqueuing an existing batch is a no-op.
* Retention of 7 days with oldest-first eviction when the stored payload
  grows past the size cap (default 256 MiB).
* Failed batches enter a ``retrying`` state and become ready again after
  ``base_backoff_seconds * 2 ** attempts`` capped at ``max_backoff_seconds``.
* Corrupt databases are quarantined and rebuilt on first use.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

__all__ = ["SQLiteBatchBuffer", "Batch", "BufferStats"]

_T = TypeVar("_T")

#: Default cap on total stored payload bytes (256 MiB).
DEFAULT_MAX_PAYLOAD_BYTES = 256 * 1024 * 1024
#: Default retention window.
DEFAULT_RETENTION_DAYS = 7
#: Default backoff bounds in seconds.
DEFAULT_BASE_BACKOFF_SECONDS = 30
DEFAULT_MAX_BACKOFF_SECONDS = 3600


@dataclass(frozen=True)
class Batch:
    """A pending batch ready (or not yet ready) for delivery."""

    batch_id: str
    payload: dict[str, Any]
    attempts: int = 0


@dataclass(frozen=True)
class BufferStats:
    pending_count: int
    payload_bytes: int
    retrying_count: int = 0
    total_count: int = 0


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    """Format a datetime as a UTC ISO-8601 string with a trailing ``Z``."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class SQLiteBatchBuffer:
    """SQLite-backed FIFO queue with backoff, retention and size limits."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS batches (
        batch_id       TEXT PRIMARY KEY,
        payload        TEXT NOT NULL,
        payload_bytes  INTEGER NOT NULL,
        status         TEXT NOT NULL CHECK (status IN ('pending', 'retrying')),
        attempts       INTEGER NOT NULL DEFAULT 0,
        next_retry_at  TEXT,
        enqueued_at    TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_batches_ready
        ON batches (status, next_retry_at, enqueued_at);
    """

    def __init__(
        self,
        path: Path,
        *,
        max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        base_backoff_seconds: int = DEFAULT_BASE_BACKOFF_SECONDS,
        max_backoff_seconds: int = DEFAULT_MAX_BACKOFF_SECONDS,
        clock: Any = None,
    ) -> None:
        self._path = Path(path)
        self._max_payload_bytes = max_payload_bytes
        self._retention = timedelta(days=retention_days)
        self._base_backoff = base_backoff_seconds
        self._max_backoff = max_backoff_seconds
        self._clock = clock or _utcnow
        self._conn: sqlite3.Connection | None = None
        self._ensure_open()

    # -- lifecycle -------------------------------------------------------

    def _ensure_open(self) -> None:
        """Open a connection, recovering from corruption if necessary."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._path), timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=10000")
            conn.executescript(self._SCHEMA)
            self._conn = conn
        except sqlite3.DatabaseError:
            self._quarantine_and_rebuild()

    def _quarantine_and_rebuild(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._conn = None
        stamp = time.strftime("%Y%m%dT%H%M%S")
        quarantine = self._path.with_suffix(self._path.suffix + f".corrupt.{stamp}")
        try:
            if self._path.exists():
                self._path.replace(quarantine)
            conn = sqlite3.connect(str(self._path), timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(self._SCHEMA)
            self._conn = conn
            logger.warning("quarantined corrupt buffer database to %s", quarantine)
        except sqlite3.DatabaseError as exc:
            logger.error("unable to rebuild buffer database at %s: %s", self._path, exc)
            raise

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._ensure_open()
        assert self._conn is not None
        return self._conn

    def _run(self, fn: Callable[[sqlite3.Connection], _T]) -> _T:
        """Run ``fn`` against a healthy connection, recovering once on error."""
        try:
            return fn(self._connect())
        except sqlite3.DatabaseError:
            logger.exception("buffer database error, attempting recovery")
            self._quarantine_and_rebuild()
            return fn(self._connect())

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -- queue operations -------------------------------------------------

    def enqueue(self, payload: dict[str, Any], now: datetime | None = None) -> bool:
        """Queue ``payload`` keyed by its ``batch_id``.

        Returns ``True`` when the batch was newly inserted and ``False``
        when a batch with the same id is already queued.
        """
        batch_id = payload.get("batch_id")
        if not isinstance(batch_id, str) or not batch_id:
            raise ValueError("payload must contain a non-empty batch_id")
        now = now or self._clock()
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        size = len(encoded.encode("utf-8"))
        when = _iso(now)

        def _insert(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO batches"
                " (batch_id, payload, payload_bytes, status, attempts, next_retry_at, enqueued_at)"
                " VALUES (?, ?, ?, 'pending', 0, NULL, ?)",
                (batch_id, encoded, size, when),
            )
            inserted = cursor.rowcount == 1
            if inserted:
                self._evict_over_capacity(conn)
            return inserted

        return bool(self._run(_insert))

    def _evict_over_capacity(self, conn: sqlite3.Connection) -> None:
        """Delete oldest batches until total payload fits the cap."""
        while True:
            total = conn.execute("SELECT COALESCE(SUM(payload_bytes), 0) FROM batches").fetchone()[
                0
            ]
            if total <= self._max_payload_bytes:
                return
            oldest = conn.execute(
                "SELECT batch_id FROM batches ORDER BY enqueued_at ASC, rowid ASC LIMIT 1"
            ).fetchone()
            if oldest is None:
                return
            conn.execute("DELETE FROM batches WHERE batch_id = ?", (oldest[0],))
            logger.warning("evicted oldest batch %s to stay within size cap", oldest[0])

    def peek_ready(self, now: datetime | None = None) -> Batch | None:
        """Return the oldest batch that is due, or ``None``."""
        now = now or self._clock()
        when = _iso(now)

        def _peek(conn: sqlite3.Connection) -> Batch | None:
            row = conn.execute(
                "SELECT batch_id, payload, attempts FROM batches"
                " WHERE status = 'pending'"
                "    OR (status = 'retrying' AND next_retry_at IS NOT NULL AND next_retry_at <= ?)"
                " ORDER BY enqueued_at ASC, rowid ASC LIMIT 1",
                (when,),
            ).fetchone()
            if row is None:
                return None
            return Batch(batch_id=row[0], payload=json.loads(row[1]), attempts=row[2])

        return self._run(_peek)

    def mark_failed(self, batch_id: str, now: datetime | None = None) -> int:
        """Mark a batch as failed and return the seconds until its retry."""
        now = now or self._clock()

        def _fail(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                "SELECT attempts FROM batches WHERE batch_id = ?", (batch_id,)
            ).fetchone()
            if row is None:
                return 0
            attempts = int(row[0]) + 1
            delay: int = min(self._base_backoff * (2 ** (attempts - 1)), self._max_backoff)
            conn.execute(
                "UPDATE batches SET status = 'retrying', attempts = ?, next_retry_at = ?"
                " WHERE batch_id = ?",
                (attempts, _iso(now + timedelta(seconds=delay)), batch_id),
            )
            return delay

        return int(self._run(_fail))

    def mark_succeeded(self, batch_id: str) -> bool:
        """Remove a delivered batch and return whether it existed."""

        def _succeed(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute("DELETE FROM batches WHERE batch_id = ?", (batch_id,))
            return cursor.rowcount > 0

        return bool(self._run(_succeed))

    def purge(self, now: datetime | None = None) -> int:
        """Delete batches older than the retention window; return the count."""
        now = now or self._clock()
        cutoff = _iso(now - self._retention)

        def _purge(conn: sqlite3.Connection) -> int:
            cursor = conn.execute("DELETE FROM batches WHERE enqueued_at < ?", (cutoff,))
            return cursor.rowcount

        return int(self._run(_purge))

    def stats(self) -> BufferStats:
        def _stats(conn: sqlite3.Connection) -> BufferStats:
            row = conn.execute(
                "SELECT COUNT(*),"
                " COALESCE(SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END), 0),"
                " COALESCE(SUM(CASE WHEN status = 'retrying' THEN 1 ELSE 0 END), 0),"
                " COALESCE(SUM(payload_bytes), 0)"
                " FROM batches"
            ).fetchone()
            return BufferStats(
                pending_count=int(row[1]),
                payload_bytes=int(row[3]),
                retrying_count=int(row[2]),
                total_count=int(row[0]),
            )

        return self._run(_stats)

    def list_batches(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return pending batches for inspection (status/status CLI)."""

        def _list(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                "SELECT batch_id, status, attempts, enqueued_at, next_retry_at, payload_bytes"
                " FROM batches ORDER BY enqueued_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                {
                    "batch_id": r[0],
                    "status": r[1],
                    "attempts": r[2],
                    "enqueued_at": r[3],
                    "next_retry_at": r[4],
                    "payload_bytes": r[5],
                }
                for r in rows
            ]

        return self._run(_list)

    # convenience accessor used by tests ----------------------------------

    def oldest_ready_time(self, batch_id: str) -> datetime | None:
        """Return the next_retry_at of a batch, or ``None`` if pending."""

        def _get(conn: sqlite3.Connection) -> datetime | None:
            row = conn.execute(
                "SELECT next_retry_at FROM batches WHERE batch_id = ?", (batch_id,)
            ).fetchone()
            if row is None or row[0] is None:
                return None
            return _parse_iso(row[0])

        return self._run(_get)
