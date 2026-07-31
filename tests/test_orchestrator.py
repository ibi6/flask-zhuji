"""Orchestrator scheduling, fault isolation and delivery behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from hostguard_agent.adapters import AdapterOutcome, BasicHardeningBaseline, UnavailableFIMProvider
from hostguard_agent.buffer import SQLiteBatchBuffer
from hostguard_agent.config import AgentConfig
from hostguard_agent.orchestrator import Orchestrator

START = datetime(2026, 1, 1, tzinfo=UTC)


class FakeCollector:
    def __init__(self, *, fail_processes: bool = False) -> None:
        self.fail_processes = fail_processes
        self.processes_calls = 0
        self.metrics_calls = 0

    def collect_metrics(self) -> dict:
        self.metrics_calls += 1
        return {
            "cpu_percent": 1.0,
            "memory_percent": 2.0,
            "disk_percent": 3.0,
            "network_bytes_sent": 1,
            "network_bytes_recv": 2,
        }

    def collect_processes(self) -> list[dict]:
        self.processes_calls += 1
        if self.fail_processes:
            raise RuntimeError("process table read failed")
        return [
            {"pid": 1, "name": "init", "executable": None, "username": None, "started_at": None}
        ]

    def collect_listening_ports(self) -> list[dict]:
        return [{"protocol": "tcp", "local_address": "0.0.0.0", "local_port": 80, "pid": 1}]

    def collect_inventory(self) -> dict:
        return {
            "hostname": "test",
            "os": "linux",
            "os_version": "x",
            "architecture": "x",
            "agent_version": "0.1.0",
        }


class FakeEvents:
    name = "events.test"

    def collect_events(self, since: datetime) -> AdapterOutcome:
        return AdapterOutcome.ok(
            [
                {
                    "event_id": "9a1f2e80-0000-4000-8000-000000000001",
                    "event_type": "login.failed",
                    "occurred_at": "2026-01-01T00:00:00Z",
                    "severity": "medium",
                    "summary": "failed login",
                }
            ]
        )


class FakeFim:
    name = "fim.test"

    def collect_changes(self, since: datetime) -> AdapterOutcome:
        return AdapterOutcome.ok(
            [
                {
                    "event_id": "9a1f2e80-0000-4000-8000-000000000002",
                    "path": "/etc/hosts",
                    "change_type": "modified",
                    "occurred_at": "2026-01-01T00:00:00Z",
                }
            ]
        )


class FakeClient:
    def __init__(self, status: int = 202) -> None:
        self.status = status
        self.posts: list[dict] = []
        self.gets = 0

    def post_json(self, path: str, payload: dict) -> SimpleNamespace:
        self.posts.append(payload)
        return SimpleNamespace(status_code=self.status, json=lambda: {})

    def get(self, path: str) -> SimpleNamespace:
        self.gets += 1
        return SimpleNamespace(status_code=200, json=lambda: {"revision": 1})

    def close(self) -> None:
        pass


def build_orchestrator(
    tmp_path: Path,
    collector: FakeCollector | None = None,
    client: FakeClient | None = None,
) -> tuple[Orchestrator, SQLiteBatchBuffer, FakeClient]:
    config = AgentConfig(
        server_url="https://hg.example",
        data_dir=tmp_path,
        collection_interval_seconds=10,
        details_interval_seconds=60,
        inventory_interval_seconds=600,
        policy_refresh_interval_seconds=300,
    )
    buffer = SQLiteBatchBuffer(tmp_path / "queue.db")
    fake_client = client or FakeClient()
    orchestrator = Orchestrator(
        config=config,
        collector=collector or FakeCollector(),
        buffer=buffer,
        client=fake_client,
        event_source=FakeEvents(),
        baseline_provider=BasicHardeningBaseline(),
        fim_provider=FakeFim(),
        clock=lambda: START,
    )
    return orchestrator, buffer, fake_client


def test_first_cycle_runs_every_job_and_builds_one_batch(tmp_path: Path) -> None:
    collector = FakeCollector()
    orchestrator, buffer, client = build_orchestrator(tmp_path, collector=collector)

    orchestrator.run_cycle(START)

    assert collector.metrics_calls == 1
    assert collector.processes_calls == 1
    assert client.gets == 1  # policy refreshed
    assert len(client.posts) == 1  # the composed batch was flushed
    batch = client.posts[0]
    assert batch["metrics"]["cpu_percent"] == 1.0
    assert "processes" in batch
    assert "listening_ports" in batch
    assert "inventory" in batch
    assert "events" in batch
    assert "file_changes" in batch
    assert "baseline_results" in batch
    assert buffer.stats().pending_count == 0


def test_schedules_respect_intervals(tmp_path: Path) -> None:
    collector = FakeCollector()
    orchestrator, buffer, client = build_orchestrator(tmp_path, collector=collector)

    orchestrator.run_cycle(START)
    # 10 seconds later: metrics + flush only.
    orchestrator.run_cycle(START + timedelta(seconds=10))
    assert collector.metrics_calls == 2
    assert collector.processes_calls == 1  # details interval is 60s
    assert client.gets == 1  # policy interval is 300s

    # 300s later: policy refresh runs again.
    orchestrator.run_cycle(START + timedelta(seconds=300))
    assert client.gets == 2

    buffer.close()


def test_failing_collector_does_not_stop_other_jobs(tmp_path: Path) -> None:
    collector = FakeCollector(fail_processes=True)
    orchestrator, buffer, client = build_orchestrator(tmp_path, collector=collector)

    orchestrator.run_cycle(START)

    assert "processes" in orchestrator.health.job_errors
    assert orchestrator.health.job_errors["processes"].detail == "process table read failed"
    assert collector.metrics_calls == 1  # metrics job still ran
    assert client.posts, "metrics batch was still produced and flushed"
    batch = client.posts[0]
    assert "metrics" in batch
    assert "processes" not in batch
    assert "inventory" in batch  # inventory job still ran

    buffer.close()


def test_server_rejection_keeps_batch_in_backoff(tmp_path: Path) -> None:
    client = FakeClient(status=500)
    orchestrator, buffer, _ = build_orchestrator(tmp_path, client=client)

    orchestrator.run_cycle(START)

    assert buffer.stats().pending_count == 0
    assert buffer.stats().retrying_count == 1
    assert orchestrator.health.batches_failed == 1
    assert buffer.peek_ready(now=START) is None  # not ready until backoff elapses

    # After backoff elapses the next cycle retries and succeeds.
    client.status = 202
    later = START + timedelta(seconds=31)
    orchestrator.run_cycle(later)
    assert buffer.stats().pending_count == 0
    assert buffer.stats().retrying_count == 0
    assert orchestrator.health.batches_sent >= 1

    buffer.close()


def test_unavailable_fim_is_reported_not_silent(tmp_path: Path) -> None:
    config = AgentConfig(server_url="https://hg.example", data_dir=tmp_path)
    buffer = SQLiteBatchBuffer(tmp_path / "queue.db")
    client = FakeClient()
    orchestrator = Orchestrator(
        config=config,
        collector=FakeCollector(),
        buffer=buffer,
        client=client,
        event_source=FakeEvents(),
        baseline_provider=BasicHardeningBaseline(),
        fim_provider=UnavailableFIMProvider("no FIM watch directories configured"),
        clock=lambda: START,
    )
    orchestrator.run_cycle(START)

    assert orchestrator.health.adapter_availability["fim"] == "unavailable"
    batch = client.posts[0]
    # The FIM unavailability is documented in the baseline checks.
    checks = batch["baseline_results"]
    assert any(c["status"] == "unavailable" and "fim" in c["check_id"] for c in checks)

    buffer.close()
