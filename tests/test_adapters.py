"""Adapter interfaces: explicit availability, no silent unsupported cases."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hostguard_agent.adapters import (
    BasicHardeningBaseline,
    CollectionStatus,
    DirectoryFIMProvider,
    LinuxJournaldEventSource,
    UnavailableEventSource,
    UnavailableFIMProvider,
    WindowsEventLogSource,
)
from hostguard_agent.collector import file_sha256


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


def test_windows_event_source_default_channels() -> None:
    source = WindowsEventLogSource()
    assert source.channels == ("System",)


def test_default_event_source_on_windows_queries_security_and_system(
    monkeypatch: object,
) -> None:
    from hostguard_agent import adapters

    monkeypatch.setattr(adapters.os, "name", "nt")
    monkeypatch.setattr(adapters.sys, "platform", "win32")
    source = adapters.default_event_source()
    assert isinstance(source, WindowsEventLogSource)
    assert source.channels == ("System", "Security")


def test_windows_event_source_set_channels_any_platform() -> None:
    source = WindowsEventLogSource()
    source.set_channels(("Security",))
    assert source.channels == ("Security",)


# -- FIM enhancements --------------------------------------------------------


def test_directory_fim_ignores_git_temp_and_backup_files(tmp_path: Path) -> None:
    watch = tmp_path / "watch"
    watch.mkdir()
    (watch / ".git").mkdir()
    (watch / ".git" / "HEAD").write_text("ref: main", encoding="utf-8")
    (watch / "scratch.tmp").write_text("temp", encoding="utf-8")
    (watch / "draft~").write_text("backup", encoding="utf-8")
    (watch / "real.conf").write_text("real", encoding="utf-8")

    fim = DirectoryFIMProvider(tmp_path, watch_dirs=(str(watch),))
    outcome = fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))

    assert outcome.status is CollectionStatus.OK
    paths = {c["path"] for c in outcome.items}
    assert any(p.endswith("real.conf") for p in paths)
    assert not any(".git" in p for p in paths)
    assert not any(p.endswith(".tmp") for p in paths)
    assert not any(p.endswith("~") for p in paths)


def test_directory_fim_large_file_threshold_skips_hashing(tmp_path: Path) -> None:
    watch = tmp_path / "watch"
    watch.mkdir()
    big = watch / "big.bin"
    big.write_bytes(b"x" * 100)

    fim = DirectoryFIMProvider(tmp_path, watch_dirs=(str(watch),), max_file_bytes=50)
    outcome = fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))

    event = next(c for c in outcome.items if c["path"].endswith("big.bin"))
    assert event["change_type"] == "created"
    assert event["sha256"] is None
    assert event["size"] == 100


def test_directory_fim_detects_permission_change(tmp_path: Path) -> None:
    watch = tmp_path / "watch"
    watch.mkdir()
    target = watch / "file.txt"
    target.write_text("data", encoding="utf-8")
    if os.name == "nt":
        os.chmod(target, 0o444)  # writable -> read-only bit change on Windows
    else:
        os.chmod(target, 0o644)

    fim = DirectoryFIMProvider(tmp_path, watch_dirs=(str(watch),))
    fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))

    if os.name == "nt":
        os.chmod(target, 0o222)  # noqa: S103 -- toggling read-only bit in a test
    else:
        os.chmod(target, 0o600)
    second = fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))

    assert any(
        c["change_type"] == "permission_changed" and c["path"].endswith("file.txt")
        for c in second.items
    )


def test_directory_fim_incremental_scan_rehashes_after_change(tmp_path: Path) -> None:
    watch = tmp_path / "watch"
    watch.mkdir()
    target = watch / "state.json"
    target.write_text('{"v": 1}', encoding="utf-8")

    fim = DirectoryFIMProvider(tmp_path, watch_dirs=(str(watch),))
    fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))

    target.write_text('{"v": 2}', encoding="utf-8")
    second = fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))

    modified = [c for c in second.items if c["path"].endswith("state.json")]
    assert len(modified) == 1
    assert modified[0]["change_type"] == "modified"
    assert modified[0]["sha256"] == file_sha256(str(target))
    assert modified[0]["size"] == len('{"v": 2}')


def test_directory_fim_history_records_before_and_after_hash(tmp_path: Path) -> None:
    watch = tmp_path / "watch"
    watch.mkdir()
    target = watch / "secret.key"
    target.write_text("v1", encoding="utf-8")

    fim = DirectoryFIMProvider(tmp_path, watch_dirs=(str(watch),))
    fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))
    target.write_text("v2", encoding="utf-8")
    fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))

    def digest(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    history = fim.fim_history()
    modified = [h for h in history if h["path"].endswith("secret.key")]
    assert modified
    assert modified[-1]["before_sha256"] == digest("v1")
    assert modified[-1]["after_sha256"] == digest("v2")
    assert modified[-1]["after_sha256"] != modified[-1]["before_sha256"]


def test_directory_fim_configure_swaps_watch_dirs(tmp_path: Path) -> None:
    first = tmp_path / "first"
    first.mkdir()
    (first / "a.txt").write_text("a", encoding="utf-8")
    second = tmp_path / "second"
    second.mkdir()

    fim = DirectoryFIMProvider(tmp_path, watch_dirs=(str(first),))
    fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))

    fim.configure((str(second),))
    (second / "b.txt").write_text("b", encoding="utf-8")
    outcome = fim.collect_changes(datetime(2026, 1, 1, tzinfo=UTC))

    assert any(c["path"].endswith("b.txt") and c["change_type"] == "created" for c in outcome.items)


# -- Linux journald ----------------------------------------------------------


class FakeRunner:
    def __init__(
        self,
        *,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        exc: Exception | None = None,
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.exc = exc
        self.args: list[str] | None = None

    def __call__(self, args: list[str]) -> tuple[int, str, str]:
        self.args = args
        if self.exc is not None:
            raise self.exc
        return self.returncode, self.stdout, self.stderr


def _journal_record(*, message: str, priority: int = 3, unit: str = "sshd.service") -> str:
    now_us = int(datetime(2026, 1, 1, 10, 0, tzinfo=UTC).timestamp() * 1_000_000)
    return json.dumps(
        {
            "__REALTIME_TIMESTAMP": str(now_us),
            "MESSAGE": message,
            "PRIORITY": str(priority),
            "_SYSTEMD_UNIT": unit,
            "_PID": "42",
            "_UID": "0",
            "__CURSOR": f"s=abc;i={hash(message) & 0xFFFF}",
        }
    )


def test_linux_journald_parses_records(monkeypatch: object) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    runner = FakeRunner(stdout=_journal_record(message="pam: authentication failure") + "\n")
    source = LinuxJournaldEventSource(runner=runner)
    outcome = source.collect_events(datetime(2026, 1, 1, 9, tzinfo=UTC))

    assert outcome.status is CollectionStatus.OK
    assert len(outcome.items) == 1
    event = outcome.items[0]
    assert event["event_type"] == "linux.journal.sshd.service"
    assert event["severity"] == "high"
    assert "authentication failure" in event["summary"]
    assert event["occurred_at"] == "2026-01-01T10:00:00Z"
    assert event["username"] == "0"
    assert runner.args is not None and runner.args[0] == "journalctl"


def test_linux_journald_severity_mapping(monkeypatch: object) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    runner = FakeRunner(
        stdout="\n".join(
            _journal_record(message=f"m{p}", priority=p, unit="app.service")
            for p in (1, 3, 4, 6)
        )
    )
    source = LinuxJournaldEventSource(runner=runner)
    outcome = source.collect_events(datetime(2026, 1, 1, 9, tzinfo=UTC))

    severities = sorted(e["severity"] for e in outcome.items)
    assert severities == ["critical", "high", "low", "medium"]


def test_linux_journald_unavailable_off_linux(monkeypatch: object) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    source = LinuxJournaldEventSource(runner=FakeRunner())
    outcome = source.collect_events(datetime(2026, 1, 1, tzinfo=UTC))

    assert outcome.status is CollectionStatus.UNAVAILABLE
    assert "Linux" in (outcome.reason or "")


def test_linux_journald_unavailable_on_missing_binary(monkeypatch: object) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    source = LinuxJournaldEventSource(runner=FakeRunner(exc=OSError("journalctl not found")))
    outcome = source.collect_events(datetime(2026, 1, 1, tzinfo=UTC))

    assert outcome.status is CollectionStatus.UNAVAILABLE
    assert "journalctl" in (outcome.reason or "")


def test_linux_journald_unavailable_on_nonzero_exit(monkeypatch: object) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    source = LinuxJournaldEventSource(
        runner=FakeRunner(returncode=1, stderr="Failed to connect to journal: Permission denied")
    )
    outcome = source.collect_events(datetime(2026, 1, 1, tzinfo=UTC))

    assert outcome.status is CollectionStatus.UNAVAILABLE
    assert "Permission denied" in (outcome.reason or "")
