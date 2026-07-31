"""Payload compatibility against contracts/telemetry.schema.json."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import jsonschema

from hostguard_agent.adapters import AdapterOutcome, BasicHardeningBaseline
from hostguard_agent.buffer import SQLiteBatchBuffer
from hostguard_agent.collector import SystemCollector
from hostguard_agent.config import AgentConfig
from hostguard_agent.orchestrator import Orchestrator

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "contracts" / "telemetry.schema.json"


def load_schema() -> dict:
    with SCHEMA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def validate(batch: dict) -> None:
    schema = load_schema()
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    errors = sorted(validator.iter_errors(batch), key=lambda e: list(e.path))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors)


def test_full_collect_batch_is_schema_compatible() -> None:
    collector = SystemCollector(clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    batch = collector.collect(include_details=True, inventory=True)
    validate(batch)
    assert batch["schema_version"] == 1
    assert batch["collected_at"].endswith("Z")


def test_minimal_metrics_batch_is_schema_compatible() -> None:
    collector = SystemCollector()
    batch = collector.collect(include_details=False, inventory=False)
    validate(batch)
    assert "inventory" not in batch
    assert "processes" not in batch


def test_baseline_unavailable_checks_are_schema_compatible() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    outcome = BasicHardeningBaseline().collect_baseline(now)
    assert outcome.status.value == "ok"
    items = outcome.items
    assert any(item["status"] == "unavailable" for item in items)
    collector = SystemCollector()
    batch = collector.collect(
        include_details=False,
        inventory=False,
        baseline_results=items,
    )
    validate(batch)


def test_event_and_file_change_shapes_are_schema_compatible() -> None:
    collector = SystemCollector()
    batch = collector.collect(
        include_details=False,
        inventory=False,
        events=[
            {
                "event_id": "9a1f2e80-0000-4000-8000-000000000001",
                "event_type": "login.failed",
                "occurred_at": "2026-01-01T00:00:00Z",
                "severity": "medium",
                "summary": "failed login for user",
                "username": "root",
            }
        ],
        file_changes=[
            {
                "event_id": "9a1f2e80-0000-4000-8000-000000000002",
                "path": "/etc/hosts",
                "change_type": "modified",
                "occurred_at": "2026-01-01T00:00:00Z",
                "sha256": "a" * 64,
                "size": 1024,
            }
        ],
    )
    validate(batch)


def test_orchestrator_produced_batch_is_schema_compatible(tmp_path) -> None:
    class FakeCollector:
        def collect_metrics(self):
            return {
                "cpu_percent": 1.0,
                "memory_percent": 2.0,
                "disk_percent": 3.0,
                "network_bytes_sent": 1,
                "network_bytes_recv": 2,
            }

        def collect_processes(self):
            return [
                {"pid": 1, "name": "init", "executable": None, "username": None, "started_at": None}
            ]

        def collect_listening_ports(self):
            return [{"protocol": "tcp", "local_address": "0.0.0.0", "local_port": 80, "pid": 1}]

        def collect_inventory(self):
            return {
                "hostname": "test",
                "os": "linux",
                "os_version": "x",
                "architecture": "x",
                "agent_version": "0.1.0",
            }

    class FakeEvents:
        name = "events.test"

        def collect_events(self, since):
            return AdapterOutcome.unavailable("no event log on this test host")

    class FakeFim:
        name = "fim.test"

        def collect_changes(self, since):
            return AdapterOutcome.ok([])

    class FakeClient:
        def __init__(self):
            self.posts = []

        def post_json(self, path, payload):
            self.posts.append(payload)
            return SimpleNamespace(status_code=202, json=lambda: {})

        def get(self, path):
            return SimpleNamespace(status_code=200, json=lambda: {"revision": 1})

        def close(self):
            pass

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
        fim_provider=FakeFim(),
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    orchestrator.run_cycle(datetime(2026, 1, 1, tzinfo=UTC))
    orchestrator.run_cycle(datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=10))
    buffer.close()

    assert client.posts, "expected at least one batch to be sent"
    for batch in client.posts:
        validate(batch)
