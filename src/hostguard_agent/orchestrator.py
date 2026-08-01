"""Scheduler/orchestrator for the collection and shipping loops.

The orchestrator runs jobs on independent schedules, isolates failures so a
single collector never stops the others, flushes the local buffer with
backoff, refreshes the remote policy and logs periodic health summaries.

Batch composition: a cycle fires zero or more section jobs; the collected
sections are combined into a single schema-compatible batch which is
enqueued once. Adapter availability problems surface as explicit
``unavailable`` baseline checks instead of silent omission.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from .adapters import AdapterOutcome, BaselineProvider, CollectionStatus, EventSource, FIMProvider
from .buffer import SQLiteBatchBuffer
from .collector import build_batch
from .config import AgentConfig
from .http_client import HttpClient
from .policy import AgentPolicy

logger = logging.getLogger(__name__)

__all__ = ["Orchestrator", "HealthState", "Collector", "JobError"]

POLICY_PATH = "/api/v1/agent/policy"
BATCHES_PATH = "/api/v1/agent/batches"

#: Maximum batches flushed per cycle to bound per-iteration work.
MAX_FLUSH_PER_CYCLE = 20


class Collector(Protocol):
    """Interface used by the orchestrator; matches SystemCollector."""

    def collect_metrics(self) -> dict[str, Any]: ...

    def collect_processes(self) -> list[dict[str, Any]]: ...

    def collect_listening_ports(self) -> list[dict[str, Any]]: ...

    def collect_inventory(self) -> dict[str, Any]: ...


@dataclass
class JobError:
    """Last failure recorded for an isolated job."""

    occurred_at: str
    detail: str


@dataclass
class HealthState:
    """Mutable health summary exposed by ``status``."""

    started_at: datetime
    job_errors: dict[str, JobError] = field(default_factory=dict)
    batches_sent: int = 0
    batches_failed: int = 0
    last_health_at: datetime | None = None
    policy_refreshed_at: str | None = None
    adapter_availability: dict[str, str] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "started_at": _iso(self.started_at),
            "batches_sent": self.batches_sent,
            "batches_failed": self.batches_failed,
            "job_errors": {name: err.detail for name, err in self.job_errors.items()},
            "policy_refreshed_at": self.policy_refreshed_at,
            "adapter_availability": self.adapter_availability,
        }


class Orchestrator:
    """Runs collection jobs on schedule and ships buffered batches."""

    def __init__(
        self,
        *,
        config: AgentConfig,
        collector: Collector,
        buffer: SQLiteBatchBuffer,
        client: HttpClient,
        event_source: EventSource,
        baseline_provider: BaselineProvider,
        fim_provider: FIMProvider,
        clock: Callable[[], datetime] | None = None,
        fim_factory: Callable[[tuple[str, ...]], FIMProvider] | None = None,
    ) -> None:
        self._config = config
        self._collector = collector
        self._buffer = buffer
        self._client = client
        self._event_source = event_source
        self._baseline_provider = baseline_provider
        self._fim_provider = fim_provider
        self._clock = clock or (lambda: datetime.now(UTC))
        self._stop_event = threading.Event()
        self._next_run: dict[str, datetime] = {}
        self._next_interval: dict[str, int] = {}
        self._last_events_poll: datetime | None = None
        self._last_fim_poll: datetime | None = None
        self._health = HealthState(started_at=self._clock())
        self._policy_path = config.data_dir / "policy.json"
        self._policy = AgentPolicy.from_payload({})
        self._policy_failures = 0
        self._fim_factory = fim_factory

    # -- public control ----------------------------------------------------

    def start(self) -> None:
        self._stop_event.clear()

    def stop(self) -> None:
        """Signal a graceful shutdown; flushes the buffer once."""
        self._stop_event.set()

    def run(self) -> None:
        """Blocking main loop until :meth:`stop` is called."""
        self.start()
        try:
            while not self._stop_event.is_set():
                now = self._clock()
                self.run_cycle(now)
                self._stop_event.wait(0.5)
        finally:
            self._flush(self._clock())
            self._client.close()
            self._buffer.close()

    def run_cycle(self, now: datetime) -> None:
        """Execute every job that is due; individual jobs are isolated."""
        sections: dict[str, Any] = {}
        adapter_checks: list[dict[str, Any]] = []
        policy = self._policy

        self._run_job("purge", lambda: self._buffer.purge(now=now), now)

        if policy.enable_metrics and self._due(
            "metrics", self._interval("collection_interval_seconds"), now
        ):
            self._run_job(
                "metrics",
                self._collector.collect_metrics,
                now,
                callback=lambda v: sections.update(metrics=v),
            )
            if policy.enable_details and self._due(
                "details", self._interval("details_interval_seconds"), now
            ):
                self._run_job(
                    "processes",
                    self._collector.collect_processes,
                    now,
                    callback=lambda v: sections.update(processes=v),
                )
                self._run_job(
                    "ports",
                    self._collector.collect_listening_ports,
                    now,
                    callback=lambda v: sections.update(listening_ports=v),
                )
            if policy.enable_events and self._due(
                "events", self._interval("details_interval_seconds"), now
            ):
                self._run_job(
                    "events",
                    self._poll_events,
                    now,
                    callback=self._attach("events", sections, adapter_checks),
                )
            if policy.enable_fim and self._due(
                "fim", self._interval("details_interval_seconds"), now
            ):
                self._run_job(
                    "fim",
                    self._poll_fim,
                    now,
                    callback=self._attach("file_changes", sections, adapter_checks),
                )
            if policy.enable_baseline and self._due(
                "baseline", self._interval("details_interval_seconds"), now
            ):
                self._run_job(
                    "baseline",
                    lambda: self._collect_baseline(now),
                    now,
                    callback=lambda v: adapter_checks.extend(v[0]),
                )
            if policy.enable_inventory and self._due(
                "inventory", self._interval("inventory_interval_seconds"), now
            ):
                self._run_job(
                    "inventory",
                    self._collector.collect_inventory,
                    now,
                    callback=lambda v: sections.update(inventory=v),
                )

        if self._due("policy", self._interval("policy_refresh_interval_seconds"), now):
            self._run_job("policy", lambda: self._refresh_policy(), now)

        if "metrics" in sections:
            batch = build_batch(collected_at=_iso(now), **sections)
            if adapter_checks:
                batch["baseline_results"] = adapter_checks[:200]
            self._run_job("enqueue", lambda: self._buffer.enqueue(batch, now=now), now)

        self._flush(now)
        self._health_log(now)

    # -- jobs --------------------------------------------------------------

    def _interval(self, name: str) -> int:
        """Resolve a scheduling interval, preferring the remote policy value."""
        value = getattr(self._policy, name)
        if value is not None:
            return int(value)
        return int(getattr(self._config, name))

    def _due(self, name: str, interval_seconds: int, now: datetime) -> bool:
        previous_interval = self._next_interval.get(name)
        next_run = self._next_run.get(name)
        if previous_interval is not None and previous_interval != interval_seconds:
            # The schedule changed (e.g. a fresh policy); re-schedule from now.
            self._next_run[name] = _add_seconds(now, interval_seconds)
            self._next_interval[name] = interval_seconds
            return True
        if next_run is None or now >= next_run:
            self._next_run[name] = _add_seconds(now, interval_seconds)
            self._next_interval[name] = interval_seconds
            return True
        return False

    def _run_job(
        self,
        name: str,
        fn: Callable[[], Any],
        now: datetime,
        *,
        callback: Callable[[Any], None] | None = None,
    ) -> None:
        """Execute a job in isolation, recording failures without stopping the cycle."""
        try:
            result = fn()
            self._health.job_errors.pop(name, None)
            if callback is not None:
                callback(result)
        except Exception as exc:  # noqa: BLE001 -- isolation boundary
            self._health.job_errors[name] = JobError(occurred_at=_iso(now), detail=str(exc))
            logger.warning("job %s failed: %s", name, exc)

    def _attach(
        self,
        key: str,
        sections: dict[str, Any],
        adapter_checks: list[dict[str, Any]],
    ) -> Callable[[tuple[list[dict[str, Any]], dict[str, Any] | None]], None]:
        """Build a callback that stores items and appends unavailable checks."""

        def _cb(result: tuple[list[dict[str, Any]], dict[str, Any] | None]) -> None:
            items, check = result
            if items:
                sections[key] = items
            if check is not None:
                adapter_checks.append(check)

        return _cb

    def _poll_events(self) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        since = self._last_events_poll or self._health.started_at
        outcome = self._event_source.collect_events(since)
        self._last_events_poll = self._clock()
        self._record_adapter_availability("events", outcome)
        check = _unavailable_check("events.adapter", outcome, self._clock)
        return _outcome_items(outcome, "events"), check

    def _poll_fim(self) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        since = self._last_fim_poll or self._health.started_at
        outcome = self._fim_provider.collect_changes(since)
        self._last_fim_poll = self._clock()
        self._record_adapter_availability("fim", outcome)
        check = _unavailable_check("fim.adapter", outcome, self._clock)
        return _outcome_items(outcome, "file_changes"), check

    def _collect_baseline(
        self, now: datetime
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        outcome = self._baseline_provider.collect_baseline(now)
        self._record_adapter_availability("baseline", outcome)
        return _outcome_items(outcome, "baseline_results"), _unavailable_check(
            "baseline.adapter", outcome, self._clock
        )

    def _record_adapter_availability(self, name: str, outcome: AdapterOutcome) -> None:
        self._health.adapter_availability[name] = outcome.status.value
        if outcome.status is not CollectionStatus.OK and outcome.reason:
            logger.warning("adapter %s unavailable: %s", name, outcome.reason)

    def _refresh_policy(self) -> None:
        """Fetch and apply the remote policy; on failure keep the last one.

        Failures back off exponentially (``base_backoff * 2 ** failures``
        capped at ``max_backoff_seconds``) by re-scheduling the next attempt.
        """
        now = self._clock()
        try:
            response = self._client.get(POLICY_PATH)
        except Exception as exc:  # noqa: BLE001 -- network boundary
            self._backoff_policy(now)
            raise RuntimeError(f"policy refresh failed: {exc}") from exc
        if response.status_code != 200:
            self._backoff_policy(now)
            raise RuntimeError(f"policy refresh returned HTTP {response.status_code}")
        payload = response.json()
        self._policy = AgentPolicy.from_payload(payload)
        self._policy_failures = 0
        self._apply_policy_to_providers()
        self._policy_path.parent.mkdir(parents=True, exist_ok=True)
        self._policy_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        self._health.policy_refreshed_at = _iso(now)

    def _backoff_policy(self, now: datetime) -> None:
        """Schedule the next policy attempt after an exponential backoff."""
        self._policy_failures += 1
        delay = min(
            self._config.base_backoff_seconds * (2 ** (self._policy_failures - 1)),
            self._config.max_backoff_seconds,
        )
        self._next_run["policy"] = _add_seconds(now, delay)

    def _apply_policy_to_providers(self) -> None:
        """Push policy-driven FIM directories / event channels to adapters."""
        watch_dirs = self._policy.fim_watch_dirs
        if watch_dirs:
            if self._fim_factory is not None:
                self._fim_provider = self._fim_factory(watch_dirs)
            elif hasattr(self._fim_provider, "configure"):
                self._fim_provider.configure(watch_dirs)
        channels = self._policy.event_channels
        if channels and hasattr(self._event_source, "set_channels"):
            self._event_source.set_channels(channels)

    # -- shipping -----------------------------------------------------------

    def _flush(self, now: datetime) -> None:
        sent = 0
        while sent < MAX_FLUSH_PER_CYCLE:
            batch = self._buffer.peek_ready(now=now)
            if batch is None:
                break
            try:
                response = self._client.post_json(BATCHES_PATH, batch.payload)
            except Exception as exc:  # noqa: BLE001 -- network boundary
                self._buffer.mark_failed(batch.batch_id, now=now)
                self._health.batches_failed += 1
                self._health.job_errors["delivery"] = JobError(
                    occurred_at=_iso(now), detail=str(exc)
                )
                break
            if response.status_code in (200, 201, 202, 409):
                # 409 means the server already accepted this batch_id.
                self._buffer.mark_succeeded(batch.batch_id)
                self._health.batches_sent += 1
            else:
                self._buffer.mark_failed(batch.batch_id, now=now)
                self._health.batches_failed += 1
                self._health.job_errors["delivery"] = JobError(
                    occurred_at=_iso(now),
                    detail=f"server rejected batch with HTTP {response.status_code}",
                )
                break
            sent += 1

    # -- health --------------------------------------------------------------

    def _health_log(self, now: datetime) -> None:
        interval = self._config.health_log_interval_seconds
        last = self._health.last_health_at
        if last is not None and now < _add_seconds(last, interval):
            return
        self._health.last_health_at = now
        stats = self._buffer.stats()
        logger.info(
            "health: sent=%d failed=%d pending=%d bytes=%d errors=%s adapters=%s",
            self._health.batches_sent,
            self._health.batches_failed,
            stats.pending_count,
            stats.payload_bytes,
            {k: v.detail for k, v in self._health.job_errors.items()} or "none",
            self._health.adapter_availability or "none",
        )

    @property
    def health(self) -> HealthState:
        return self._health


def _outcome_items(outcome: AdapterOutcome, section: str) -> list[dict[str, Any]]:
    if outcome.status is CollectionStatus.OK:
        return outcome.items
    return []


def _unavailable_check(
    check_id: str,
    outcome: AdapterOutcome,
    clock: Callable[[], datetime],
) -> dict[str, Any] | None:
    """Build an explicit ``unavailable`` baseline check for a failed adapter."""
    if outcome.status is CollectionStatus.OK:
        return None
    return {
        "check_id": check_id,
        "status": "unavailable",
        "checked_at": _iso(clock()),
        "message": (outcome.reason or "collection unavailable")[:1024],
    }


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _add_seconds(value: datetime, seconds: int) -> datetime:
    return value + timedelta(seconds=seconds)
