"""Inventory baseline scanning: snapshot establishment and drift detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from hostguard_agent.adapters import CollectionStatus
from hostguard_agent.baseline import (
    BaselineResult,
    InventoryBaselineProvider,
    InventorySnapshot,
)
from hostguard_agent.collector import SystemCollector

START = datetime(2026, 1, 1, 8, tzinfo=UTC)


def _service(name: str, state: str = "running") -> dict:
    return {"name": name, "state": state, "start_type": "auto"}


def _software(name: str, version: str) -> dict:
    return {"name": name, "version": version, "vendor": None}


def _port(protocol: str, local_port: int) -> dict:
    return {"protocol": protocol, "local_address": "0.0.0.0", "local_port": local_port, "pid": 1}


def _collectors(
    *,
    services: list[dict] | None = None,
    software: list[dict] | None = None,
    startup_items: list[dict] | None = None,
    ports: list[dict] | None = None,
    error: str | None = None,
) -> dict:
    def _ok(items: list[dict]) -> tuple[list[dict], str | None]:
        return items, error

    return {
        "services": lambda: _ok(list(services or [])),
        "software": lambda: _ok(list(software or [])),
        "startup_items": lambda: _ok(list(startup_items or [])),
        "listening_ports": lambda: _ok(list(ports or [])),
    }


def test_first_scan_establishes_baseline(tmp_path: Path) -> None:
    provider = InventoryBaselineProvider(
        tmp_path,
        collectors=_collectors(services=[_service("ssh")], ports=[_port("tcp", 22)]),
    )

    outcome = provider.collect_baseline(START)

    assert outcome.status is CollectionStatus.OK
    assert any(item["check_id"] == "baseline.established" and item["status"] == "pass"
               for item in outcome.items)
    assert (tmp_path / "baseline_inventory.json").exists()


def test_second_scan_detects_service_and_port_drift(tmp_path: Path) -> None:
    provider = InventoryBaselineProvider(
        tmp_path,
        collectors=_collectors(services=[_service("ssh")], ports=[_port("tcp", 22)]),
    )
    provider.collect_baseline(START)

    provider = InventoryBaselineProvider(
        tmp_path,
        collectors=_collectors(
            services=[_service("ssh"), _service("nginx")],
            ports=[_port("tcp", 22), _port("tcp", 80)],
        ),
    )
    outcome = provider.collect_baseline(START + timedelta(minutes=1))

    checks = {item["check_id"]: item["status"] for item in outcome.items}
    assert checks["baseline.services"] == "fail"
    assert checks["baseline.listening_ports"] == "fail"
    services = next(i for i in outcome.items if i["check_id"] == "baseline.services")
    assert "added" in services["message"]
    assert "nginx" in services["message"]


def test_unchanged_scan_is_pass(tmp_path: Path) -> None:
    collector_factory = lambda: _collectors(  # noqa: E731
        services=[_service("ssh")],
        software=[_software("openssh", "9.0")],
        startup_items=[{"name": "ssh", "command": "/usr/sbin/sshd"}],
        ports=[_port("tcp", 22)],
    )
    provider = InventoryBaselineProvider(tmp_path, collectors=collector_factory())
    provider.collect_baseline(START)

    outcome = InventoryBaselineProvider(tmp_path, collectors=collector_factory()).collect_baseline(
        START
    )
    checks = {item["check_id"]: item["status"] for item in outcome.items}
    assert checks["baseline.system"] == "pass"
    assert checks["baseline.services"] == "pass"
    assert checks["baseline.software"] == "pass"
    assert checks["baseline.startup_items"] == "pass"
    assert checks["baseline.listening_ports"] == "pass"


def test_failing_collector_reports_unavailable(tmp_path: Path) -> None:
    provider = InventoryBaselineProvider(
        tmp_path,
        collectors=_collectors(services=[_service("ssh")]),
    )
    provider.collect_baseline(START)

    provider = InventoryBaselineProvider(
        tmp_path,
        collectors=_collectors(
            services=[_service("ssh")], ports=[_port("tcp", 22)], error="access denied"
        ),
    )
    outcome = provider.collect_baseline(START)

    software = next(i for i in outcome.items if i["check_id"] == "baseline.software")
    assert software["status"] == "unavailable"
    assert "access denied" in software["message"]


def test_snapshot_dataclass_round_trip(tmp_path: Path) -> None:
    snapshot = InventorySnapshot(
        collected_at="2026-01-01T08:00:00Z",
        system={"hostname": "test-host", "os": "linux"},
        services=[_service("ssh")],
        software=[],
        startup_items=[],
        listening_ports=[],
    )
    restored = InventorySnapshot.from_dict(snapshot.as_dict())
    assert restored == snapshot


def test_baseline_result_dict_is_schema_compatible() -> None:
    result = BaselineResult(
        check_id="baseline.services", status="fail", checked_at="2026-01-01T08:00:00Z",
        message="added 1: ('nginx', 'running')",
    ).as_dict()
    assert result["status"] == "fail"
    assert result["message"]


def test_baseline_results_validate_against_schema(tmp_path: Path) -> None:
    provider = InventoryBaselineProvider(
        tmp_path,
        collectors=_collectors(services=[_service("ssh")], ports=[_port("tcp", 22)]),
    )
    outcome = provider.collect_baseline(START)

    from test_schema import validate

    collector = SystemCollector()
    batch = collector.collect(
        include_details=False, inventory=False, baseline_results=outcome.items
    )
    validate(batch)
