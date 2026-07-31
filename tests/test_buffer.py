from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from hostguard_agent.buffer import SQLiteBatchBuffer


def test_queue_is_idempotent_and_returns_oldest_ready_batch(tmp_path: Path) -> None:
    queue = SQLiteBatchBuffer(tmp_path / "queue.db")
    first = {"batch_id": "4690f45c-1696-4ad5-b7b3-18f30a0ecc52", "value": 1}
    second = {"batch_id": "261c6ba7-826c-4a85-a3fb-4702982e54e3", "value": 2}

    assert queue.enqueue(first) is True
    assert queue.enqueue(first) is False
    assert queue.enqueue(second) is True

    assert queue.peek_ready().payload == first
    assert queue.stats().pending_count == 2


def test_failed_batch_uses_bounded_exponential_backoff(tmp_path: Path) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    queue = SQLiteBatchBuffer(tmp_path / "queue.db", base_backoff_seconds=5, max_backoff_seconds=20)
    batch_id = "4690f45c-1696-4ad5-b7b3-18f30a0ecc52"
    queue.enqueue({"batch_id": batch_id}, now=now)

    assert queue.mark_failed(batch_id, now=now) == 5
    assert queue.peek_ready(now=now + timedelta(seconds=4)) is None
    assert queue.peek_ready(now=now + timedelta(seconds=5)) is not None
    assert queue.mark_failed(batch_id, now=now + timedelta(seconds=5)) == 10
    assert queue.mark_failed(batch_id, now=now + timedelta(seconds=15)) == 20
    assert queue.mark_failed(batch_id, now=now + timedelta(seconds=35)) == 20


def test_success_removes_batch_and_old_entries_expire(tmp_path: Path) -> None:
    now = datetime(2026, 1, 8, tzinfo=UTC)
    queue = SQLiteBatchBuffer(tmp_path / "queue.db", retention_days=7)
    old_id = "4690f45c-1696-4ad5-b7b3-18f30a0ecc52"
    new_id = "261c6ba7-826c-4a85-a3fb-4702982e54e3"
    queue.enqueue({"batch_id": old_id}, now=now - timedelta(days=8))
    queue.enqueue({"batch_id": new_id}, now=now)

    assert queue.purge(now=now) == 1
    assert queue.mark_succeeded(new_id) is True
    assert queue.stats().pending_count == 0


def test_size_limit_evicts_oldest_batches(tmp_path: Path) -> None:
    queue = SQLiteBatchBuffer(tmp_path / "queue.db", max_payload_bytes=180)
    queue.enqueue({"batch_id": "4690f45c-1696-4ad5-b7b3-18f30a0ecc52", "data": "a" * 80})
    queue.enqueue({"batch_id": "261c6ba7-826c-4a85-a3fb-4702982e54e3", "data": "b" * 80})

    stats = queue.stats()
    assert stats.payload_bytes <= 180
    assert stats.pending_count == 1
    assert queue.peek_ready().batch_id == "261c6ba7-826c-4a85-a3fb-4702982e54e3"
