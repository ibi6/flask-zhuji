"""Adapter interfaces: explicit availability, no silent unsupported cases."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hostguard_agent.adapters import (
    BasicHardeningBaseline,
    CollectionStatus,
    DirectoryFIMProvider,
    UnavailableEventSource,
    UnavailableFIMProvider,
    WindowsEventLogSource,
)


def test_unavailable_event_source_is_explicit() -> None:
    source = UnavailableEventSource("the event log cannot be read here")
    outcome = source.collect_events(datetime(2026, 1, 1, tzinfo=UTC))
    assert outcome.status is CollectionStatus.UNAVAILABLE
    assert outcome.reason == "the event log cannot be read here"
    assert outcome.items == []


def test_unavailable_fim_is_explicit() -> None:
    fim = UnavailableFIMProvider("no watch directories configured")
    outcome = fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))
    assert outcome.status is CollectionStatus.UNAVAILABLE
    assert outcome.reason == "no watch directories configured"


def test_baseline_provider_reports_unavailable_checks() -> None:
    outcome = BasicHardeningBaseline().collect_baseline(datetime(2026, 1, 1, tzinfo=UTC))
    assert outcome.status is CollectionStatus.OK
    statuses = {item["check_id"]: item["status"] for item in outcome.items}
    assert statuses["firewall.status"] == "unavailable"
    assert statuses["os.patch_level"] == "unavailable"
    assert statuses["disk.root.usage"] in {"pass", "fail"}
    for item in outcome.items:
        assert item["message"]


def test_directory_fim_without_watch_dirs_is_unavailable(tmp_path: Path) -> None:
    fim = DirectoryFIMProvider(tmp_path)
    outcome = fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))
    assert outcome.status is CollectionStatus.UNAVAILABLE


def test_directory_fim_detects_create_modify_delete(tmp_path: Path) -> None:
    watch = tmp_path / "watch"
    watch.mkdir()
    target = watch / "config.txt"
    target.write_text("v1", encoding="utf-8")
    fim = DirectoryFIMProvider(tmp_path, watch_dirs=(str(watch),))

    first = fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))
    assert first.status is CollectionStatus.OK
    assert any(c["change_type"] == "created" for c in first.items)

    target.write_text("v2", encoding="utf-8")
    second = fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))
    assert any(c["change_type"] == "modified" for c in second.items)

    target.unlink()
    third = fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))
    assert any(c["change_type"] == "deleted" for c in third.items)


def test_windows_event_source_smoke() -> None:
    """On Windows the adapter must return a structured outcome, never throw."""
    if os.name != "nt":
        outcome = WindowsEventLogSource().collect_events(datetime(2026, 1, 1, tzinfo=UTC))
        assert outcome.status is CollectionStatus.UNAVAILABLE
        return
    outcome = WindowsEventLogSource().collect_events(datetime.now(UTC) - timedelta(hours=1))
    assert outcome.status in {CollectionStatus.OK, CollectionStatus.UNAVAILABLE}
