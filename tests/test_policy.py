"""Policy execution: parsing, scheduling, toggles, provider application, backoff."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from hostguard_agent.adapters import AdapterOutcome, BasicHardeningBaseline
from hostguard_agent.buffer import SQLiteBatchBuffer
from hostguard_agent.config import AgentConfig
from hostguard_agent.orchestrator import Orchestrator
from hostguard_agent.policy import AgentPolicy

START = datetime(2026, 1, 1, tzinfo=UTC)


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> None:
        self.value += delta


class FakeCollector:
    def __init__(self) -> None:
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
        return []

    def collect_listening_ports(self) -> list[dict]:
        return []

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

    def __init__(self) -> None:
        self.channels: tuple[str, ...] = ()

    def set_channels(self, channels: tuple[str, ...]) -> None:
        self.channels = tuple(channels)

    def collect_events(self, since: datetime) -> AdapterOutcome:
        return AdapterOutcome.ok([])


class FakeFim:
    name = "fim.test"

    def __init__(self) -> None:
        self.watch_dirs: tuple[str, ...] = ()

    def configure(self, watch_dirs: tuple[str, ...]) -> None:
        self.watch_dirs = tuple(watch_dirs)

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
    def __init__(self, policy: dict | None = None, status: int = 200) -> None:
        self.policy = policy or {"revision": "r1"}
        self.status = status
        self.gets = 0
        self.posts: list[dict] = []

    def get(self, path: str):
        self.gets += 1
        return SimpleNamespace(status_code=self.status, json=lambda: self.policy)

    def post_json(self, path: str, payload: dict):
        self.posts.append(payload)
        return SimpleNamespace(status_code=202, json=lambda: {})

    def close(self) -> None:
        pass


def build_orchestrator(
    tmp_path: Path,
    *,
    policy: dict | None = None,
    status: int = 200,
    fim_factory=None,
) -> tuple[Orchestrator, SQLiteBatchBuffer, FakeClient, FakeEvents, FakeFim, MutableClock]:
    config = AgentConfig(
        server_url="https://hg.example",
        data_dir=tmp_path,
        base_backoff_seconds=30,
        max_backoff_seconds=120,
        policy_refresh_interval_seconds=300,
    )
    buffer = SQLiteBatchBuffer(tmp_path / "queue.db")
    client = FakeClient(policy=policy, status=status)
    events = FakeEvents()
    fim = FakeFim()
    clock = MutableClock(START)
    orchestrator = Orchestrator(
        config=config,
        collector=FakeCollector(),
        buffer=buffer,
        client=client,
        event_source=events,
        baseline_provider=BasicHardeningBaseline(),
        fim_provider=fim,
        fim_factory=fim_factory,
        clock=clock,
    )
    return orchestrator, buffer, client, events, fim, clock


def test_policy_from_payload_parses_fields() -> None:
    policy = AgentPolicy.from_payload(
        {
            "revision": "rev-7",
            "collection_interval_seconds": 15,
            "details_interval_seconds": 120,
            "enable_events": False,
            "enable_metrics": "false",
            "fim_watch_dirs": ["/etc", "/opt/app/config"],
            "event_channels": ["System", "Security"],
        }
    )
    assert policy.revision == "rev-7"
    assert policy.collection_interval_seconds == 15
    assert policy.details_interval_seconds == 120
    assert policy.enable_events is False
    assert policy.enable_metrics is False
    assert policy.fim_watch_dirs == ("/etc", "/opt/app/config")
    assert policy.event_channels == ("System", "Security")


def test_policy_empty_payload_uses_defaults() -> None:
    policy = AgentPolicy.from_payload({})
    assert policy.enable_metrics is True
    assert policy.enable_fim is True
    assert policy.collection_interval_seconds is None
    assert policy.fim_watch_dirs == ()


def test_policy_interval_applies_to_scheduler(tmp_path: Path) -> None:
    orchestrator, buffer, client, _, _, _ = build_orchestrator(
        tmp_path, policy={"revision": "r1", "collection_interval_seconds": 3}
    )
    collector = orchestrator._collector  # type: ignore[attr-defined]

    orchestrator.run_cycle(START)
    assert collector.metrics_calls == 1
    # Policy (interval 3s) has taken over from the local 10s default.
    orchestrator.run_cycle(START + timedelta(seconds=5))
    assert collector.metrics_calls == 2
    buffer.close()


def test_policy_toggle_disables_events_section(tmp_path: Path) -> None:
    orchestrator, buffer, client, _, _, clock = build_orchestrator(
        tmp_path, policy={"revision": "r1", "enable_events": False}
    )
    orchestrator.run_cycle(START)  # first cycle applies the policy
    clock.advance(timedelta(seconds=60))
    orchestrator.run_cycle(clock.value)

    assert client.posts
    batch = client.posts[-1]
    assert "events" not in batch
    assert "file_changes" in batch  # FIM still enabled
    buffer.close()


def test_policy_toggle_disables_fim(tmp_path: Path) -> None:
    orchestrator, buffer, client, _, _, clock = build_orchestrator(
        tmp_path, policy={"revision": "r1", "enable_fim": False, "enable_baseline": False}
    )
    orchestrator.run_cycle(START)
    clock.advance(timedelta(seconds=60))
    orchestrator.run_cycle(clock.value)

    assert client.posts
    batch = client.posts[-1]
    assert "file_changes" not in batch
    assert "baseline_results" not in batch
    buffer.close()


def test_policy_fim_dirs_configure_provider(tmp_path: Path) -> None:
    orchestrator, buffer, _, _, fim, _ = build_orchestrator(
        tmp_path, policy={"revision": "r1", "fim_watch_dirs": ["/etc"]}
    )
    orchestrator.run_cycle(START)

    assert fim.watch_dirs == ("/etc",)
    buffer.close()


def test_policy_fim_factory_rebuilds_provider(tmp_path: Path) -> None:
    created: list[tuple[str, ...]] = []

    def factory(watch_dirs: tuple[str, ...]) -> FakeFim:
        created.append(watch_dirs)
        provider = FakeFim()
        provider.watch_dirs = watch_dirs
        return provider

    orchestrator, buffer, _, _, initial_fim, _ = build_orchestrator(
        tmp_path,
        policy={"revision": "r1", "fim_watch_dirs": ["/srv"]},
        fim_factory=factory,
    )
    orchestrator.run_cycle(START)

    assert created == [("/srv",)]
    assert orchestrator._fim_provider is not initial_fim  # type: ignore[attr-defined]
    buffer.close()


def test_policy_channels_configure_event_source(tmp_path: Path) -> None:
    orchestrator, buffer, _, events, _, _ = build_orchestrator(
        tmp_path, policy={"revision": "r1", "event_channels": ["Security"]}
    )
    orchestrator.run_cycle(START)

    assert events.channels == ("Security",)
    buffer.close()


def test_policy_refresh_failure_keeps_last_policy_and_backs_off(tmp_path: Path) -> None:
    orchestrator, buffer, client, _, _, clock = build_orchestrator(
        tmp_path, policy={"revision": "r1", "collection_interval_seconds": 3}, status=500
    )

    orchestrator.run_cycle(START)
    assert "policy" in orchestrator.health.job_errors
    assert orchestrator.health.policy_refreshed_at is None
    assert orchestrator._next_run["policy"] == START + timedelta(seconds=30)  # type: ignore[attr-defined]

    # Backoff doubles after a second consecutive failure.
    clock.advance(timedelta(seconds=30))
    orchestrator.run_cycle(clock.value)
    assert orchestrator._next_run["policy"] == START + timedelta(seconds=90)  # type: ignore[attr-defined]

    # Recovery: the next attempt succeeds and the error is cleared.
    clock.advance(timedelta(seconds=60))
    client.status = 200
    orchestrator.run_cycle(clock.value)
    assert "policy" not in orchestrator.health.job_errors
    assert orchestrator.health.policy_refreshed_at is not None
    assert orchestrator._next_run["policy"] == START + timedelta(seconds=390)  # type: ignore[attr-defined]
    buffer.close()


def test_policy_failure_applies_no_intervals(tmp_path: Path) -> None:
    orchestrator, buffer, _, _, _, clock = build_orchestrator(
        tmp_path, policy={"revision": "r1", "collection_interval_seconds": 3}, status=500
    )
    collector = orchestrator._collector  # type: ignore[attr-defined]

    orchestrator.run_cycle(START)
    # Policy failed: the local 10s interval stays in effect, so +5s is not due.
    clock.advance(timedelta(seconds=5))
    orchestrator.run_cycle(clock.value)
    assert collector.metrics_calls == 1
    buffer.close()
