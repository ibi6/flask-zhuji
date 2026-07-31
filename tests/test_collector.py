from __future__ import annotations

from datetime import UTC, datetime

import psutil

from hostguard_agent.collector import SystemCollector


def test_collect_builds_schema_compatible_public_telemetry(monkeypatch: object) -> None:
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 12.5)  # type: ignore[attr-defined]
    monkeypatch.setattr(psutil, "virtual_memory", lambda: type("VM", (), {"percent": 34.5})())  # type: ignore[attr-defined]
    monkeypatch.setattr(psutil, "disk_usage", lambda path: type("DU", (), {"percent": 56.5})())  # type: ignore[attr-defined]
    monkeypatch.setattr(  # type: ignore[attr-defined]
        psutil,
        "net_io_counters",
        lambda: type("NET", (), {"bytes_sent": 100, "bytes_recv": 200})(),
    )
    collector = SystemCollector(clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))

    payload = collector.collect(include_details=False)

    assert payload["schema_version"] == 1
    assert payload["collected_at"] == "2026-01-01T00:00:00Z"
    assert payload["metrics"] == {
        "cpu_percent": 12.5,
        "memory_percent": 34.5,
        "disk_percent": 56.5,
        "network_bytes_sent": 100,
        "network_bytes_recv": 200,
    }
    assert payload["inventory"]["hostname"]
    assert payload["inventory"]["os"] in {"windows", "linux"}
    assert "cmdline" not in str(payload)
    assert "environ" not in str(payload)


def test_process_and_listening_port_collection_handles_access_denied(monkeypatch: object) -> None:
    class Process:
        info = {"pid": 7, "name": "service", "exe": None, "username": None, "create_time": None}

    monkeypatch.setattr(psutil, "process_iter", lambda attrs: [Process()])  # type: ignore[attr-defined]
    monkeypatch.setattr(  # type: ignore[attr-defined]
        psutil,
        "net_connections",
        lambda kind: (_ for _ in ()).throw(psutil.AccessDenied()),
    )
    collector = SystemCollector()

    assert collector.collect_processes() == [
        {"pid": 7, "name": "service", "executable": None, "username": None, "started_at": None}
    ]
    assert collector.collect_listening_ports() == []
