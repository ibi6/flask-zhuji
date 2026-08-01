"""Collector adapters for events, baseline checks and file integrity.

This module defines the collection interfaces and ships concrete adapters.
Every adapter reports its availability explicitly; unsupported platforms or
missing privileges produce an :class:`AdapterOutcome` with status
``unavailable`` and a factual reason. There are no ``TODO`` placeholders:
an adapter that cannot run states exactly why it cannot.

Adapters
--------

* :class:`WindowsEventLogSource` -- reads one or more Windows event log
  channels (Security/System) via ``wevtapi`` (ctypes). Degrades to
  ``unavailable`` with the concrete reason on any API failure.
* :class:`LinuxJournaldEventSource` -- reads journald records via
  ``journalctl --output=json``; ``unavailable`` when journald is missing or
  permission is denied.
* :class:`UnavailableEventSource` -- explicit unavailable outcome.
* :class:`BasicHardeningBaseline` -- cross-platform checks (disk/memory) plus
  platform-specific checks reported as ``unavailable``.
* :class:`DirectoryFIMProvider` -- file integrity monitoring over configured
  directories with a persistent manifest, ignore rules, a large-file
  threshold, incremental re-hashing and a before/after hash history;
  ``unavailable`` when no watch directories are configured.
* :class:`UnavailableFIMProvider` / :class:`UnavailableBaselineProvider` --
  explicit unavailable outcomes for platforms with no implementation.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import json
import logging
import os
import stat
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast

from .collector import file_sha256, utcnow_iso

logger = logging.getLogger(__name__)

__all__ = [
    "CollectionStatus",
    "AdapterOutcome",
    "EventSource",
    "BaselineProvider",
    "FIMProvider",
    "UnavailableEventSource",
    "UnavailableBaselineProvider",
    "UnavailableFIMProvider",
    "BasicHardeningBaseline",
    "DirectoryFIMProvider",
    "WindowsEventLogSource",
    "LinuxJournaldEventSource",
    "default_event_source",
    "default_baseline_provider",
    "default_fim_provider",
]


class CollectionStatus(StrEnum):
    """Explicit outcome of an adapter collection pass."""

    OK = "ok"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass(frozen=True)
class AdapterOutcome:
    """Result of an adapter collection.

    ``items`` holds schema-compatible records when ``status`` is ``ok`` and
    is empty otherwise; ``reason`` explains unavailability or errors.
    """

    status: CollectionStatus
    items: list[dict[str, Any]] = field(default_factory=list)
    reason: str | None = None

    @classmethod
    def ok(cls, items: list[dict[str, Any]]) -> AdapterOutcome:
        return cls(status=CollectionStatus.OK, items=items)

    @classmethod
    def unavailable(cls, reason: str) -> AdapterOutcome:
        return cls(status=CollectionStatus.UNAVAILABLE, reason=reason)

    @classmethod
    def error(cls, reason: str) -> AdapterOutcome:
        return cls(status=CollectionStatus.ERROR, reason=reason)


class EventSource(Protocol):
    """Adapter that yields security-relevant host events."""

    name: str

    def collect_events(self, since: datetime) -> AdapterOutcome: ...


class BaselineProvider(Protocol):
    """Adapter that evaluates host hardening baseline checks."""

    name: str

    def collect_baseline(self, checked_at: datetime) -> AdapterOutcome: ...


class FIMProvider(Protocol):
    """Adapter that reports file integrity changes."""

    name: str

    def collect_changes(self, since: datetime) -> AdapterOutcome: ...


# -- explicit unavailable implementations ---------------------------------


class UnavailableEventSource:
    """Event source that is unavailable on the current host."""

    name = "events.unavailable"

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def collect_events(self, since: datetime) -> AdapterOutcome:
        return AdapterOutcome.unavailable(self._reason)


class UnavailableBaselineProvider:
    """Baseline provider unavailable on the current host."""

    name = "baseline.unavailable"

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def collect_baseline(self, checked_at: datetime) -> AdapterOutcome:
        return AdapterOutcome.unavailable(self._reason)


class UnavailableFIMProvider:
    """FIM adapter unavailable on the current host."""

    name = "fim.unavailable"

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def collect_changes(self, since: datetime) -> AdapterOutcome:
        return AdapterOutcome.unavailable(self._reason)


# -- baseline -------------------------------------------------------------


class BasicHardeningBaseline:
    """A small set of cross-platform baseline checks.

    Checks that need platform-specific privileges or tooling report
    ``unavailable`` with the concrete reason instead of being skipped.
    """

    name = "baseline.basic"

    def collect_baseline(self, checked_at: datetime) -> AdapterOutcome:
        import psutil

        checked = _iso(checked_at)
        results: list[dict[str, Any]] = []
        try:
            disk_percent = psutil.disk_usage("/").percent
            results.append(
                {
                    "check_id": "disk.root.usage",
                    "status": "pass" if disk_percent < 90 else "fail",
                    "checked_at": checked,
                    "message": f"root filesystem usage {disk_percent:.1f}%",
                }
            )
        except (OSError, psutil.Error) as exc:
            results.append(_unavailable_check("disk.root.usage", checked, str(exc)))
        try:
            memory_percent = psutil.virtual_memory().percent
            results.append(
                {
                    "check_id": "memory.utilization",
                    "status": "pass" if memory_percent < 90 else "fail",
                    "checked_at": checked,
                    "message": f"memory usage {memory_percent:.1f}%",
                }
            )
        except (OSError, psutil.Error) as exc:
            results.append(_unavailable_check("memory.utilization", checked, str(exc)))
        results.append(
            _unavailable_check(
                "firewall.status",
                checked,
                "querying firewall state requires elevated privileges and platform-specific APIs",
            )
        )
        results.append(
            _unavailable_check(
                "os.patch_level",
                checked,
                "patch level requires an update channel that the agent runtime "
                "does not expose on this host",
            )
        )
        return AdapterOutcome.ok(results)


def _unavailable_check(check_id: str, checked_at: str, message: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "unavailable",
        "checked_at": checked_at,
        "message": message[:1024],
    }


# -- file integrity -------------------------------------------------------


class DirectoryFIMProvider:
    """FIM over configured directories with a persistent hash manifest.

    A pass walks every watch directory (honoring ignore rules), computes a
    snapshot (hash, size, mtime, permission mode) and diffs it against the
    stored manifest. Detected changes are emitted as schema-compatible
    ``file_changes`` records; the previous hash is retained in a bounded
    history file so every change carries a before/after hash pair.

    * Ignore rules: directory/file names in ``ignore_names`` (``.git``),
      suffixes in ``ignore_suffixes`` (temp/backup files) and prefixes in
      ``ignore_prefixes`` are skipped entirely.
    * Large files: when ``max_file_bytes`` is set, larger files are tracked by
      metadata only (``sha256`` is ``None``) so hashing cost stays bounded.
    * Incremental scanning: content hashing is skipped when size + mtime are
      unchanged, so unchanged trees only pay ``stat`` cost.
    """

    name = "fim.directory"

    _HISTORY_LIMIT = 500

    def __init__(
        self,
        data_dir: Path,
        watch_dirs: tuple[str, ...] = (),
        *,
        ignore_names: tuple[str, ...] = (".git",),
        ignore_suffixes: tuple[str, ...] = (".tmp", ".swp", ".lock", "~"),
        ignore_prefixes: tuple[str, ...] = (".#",),
        max_file_bytes: int | None = None,
        manifest_name: str = "fim_manifest.json",
        history_name: str = "fim_history.json",
    ) -> None:
        self._manifest_path = Path(data_dir) / manifest_name
        self._history_path = Path(data_dir) / history_name
        self._watch_dirs = tuple(str(Path(d)) for d in watch_dirs)
        self._ignore_names = tuple(ignore_names)
        self._ignore_suffixes = tuple(ignore_suffixes)
        self._ignore_prefixes = tuple(ignore_prefixes)
        self._max_file_bytes = max_file_bytes

    def configure(self, watch_dirs: tuple[str, ...]) -> None:
        """Replace the watched directories (used by policy application)."""
        self._watch_dirs = tuple(str(Path(d)) for d in watch_dirs)

    def fim_history(self, limit: int = _HISTORY_LIMIT) -> list[dict[str, Any]]:
        """Recent change records including before/after hashes."""
        return self._load_list(self._history_path)[-limit:]

    def collect_changes(self, since: datetime) -> AdapterOutcome:
        if not self._watch_dirs:
            return AdapterOutcome.unavailable("no FIM watch directories configured")
        manifest = self._load_dict(self._manifest_path)
        history = self._load_list(self._history_path)
        current: dict[str, dict[str, Any]] = {}
        changes: list[dict[str, Any]] = []
        for watch_dir in self._watch_dirs:
            root = Path(watch_dir)
            if not root.is_dir():
                continue
            for path in self._iter_files(root):
                record = self._inspect_file(path, manifest)
                if record is None:
                    continue
                key = os.path.abspath(str(path))
                current[key] = record
                previous = manifest.get(key)
                change = self._diff_change(previous, record)
                if change is None:
                    continue
                change["event_id"] = str(uuid.uuid4())
                change["path"] = key[:2048]
                changes.append(change)
                self._record_history(history, change, previous, record)
        for key in sorted(set(manifest) - set(current)):
            previous = manifest[key]
            change = {
                "event_id": str(uuid.uuid4()),
                "path": key[:2048],
                "change_type": "deleted",
                "occurred_at": utcnow_iso(),
                "sha256": previous.get("sha256"),
                "size": previous.get("size"),
            }
            changes.append(change)
            self._record_history(history, change, previous, None)
        self._save_json(self._manifest_path, current)
        self._save_json(self._history_path, history[-self._HISTORY_LIMIT :])
        return AdapterOutcome.ok(changes)

    def _iter_files(self, root: Path) -> Any:
        """Depth-first yield of non-ignored regular files under ``root``."""
        stack = [root]
        while stack:
            current = stack.pop()
            try:
                entries = sorted(os.scandir(current), key=lambda e: e.name)
            except OSError:
                continue
            for entry in entries:
                if self._is_ignored(entry.name):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    yield Path(entry.path)

    def _is_ignored(self, name: str) -> bool:
        if name in self._ignore_names:
            return True
        if any(name.startswith(prefix) for prefix in self._ignore_prefixes):
            return True
        if any(name.endswith(suffix) for suffix in self._ignore_suffixes):
            return True
        return False

    def _inspect_file(
        self, path: Path, manifest: dict[str, dict[str, Any]]
    ) -> dict[str, Any] | None:
        try:
            st = path.stat()
        except OSError:
            return None
        key = os.path.abspath(str(path))
        previous = manifest.get(key)
        size = int(st.st_size)
        mtime = float(st.st_mtime)
        mode = int(stat.S_IMODE(st.st_mode))
        large = self._max_file_bytes is not None and size > self._max_file_bytes
        sha256: str | None = None
        if not large:
            prev_large = bool((previous or {}).get("large"))
            unchanged = (
                previous is not None
                and not prev_large
                and previous.get("size") == size
                and abs(float(previous.get("mtime", -1)) - mtime) < 1e-9
            )
            if unchanged and previous is not None:
                sha256 = previous.get("sha256")
            else:
                try:
                    sha256 = file_sha256(str(path))
                except OSError:
                    return None
        return {
            "sha256": sha256,
            "size": size,
            "mtime": mtime,
            "mode": mode,
            "large": large,
            "occurred_at": _iso(datetime.fromtimestamp(st.st_mtime, tz=UTC)),
        }

    def _diff_change(
        self, previous: dict[str, Any] | None, record: dict[str, Any]
    ) -> dict[str, Any] | None:
        if previous is None:
            return {
                "change_type": "created",
                "occurred_at": record["occurred_at"],
                "sha256": record["sha256"],
                "size": record["size"],
            }
        if record["sha256"] != previous.get("sha256"):
            return {
                "change_type": "modified",
                "occurred_at": record["occurred_at"],
                "sha256": record["sha256"],
                "size": record["size"],
            }
        if previous.get("large") and (
            record["size"] != previous.get("size") or record["mtime"] != previous.get("mtime")
        ):
            return {
                "change_type": "modified",
                "occurred_at": record["occurred_at"],
                "sha256": None,
                "size": record["size"],
            }
        if record["mode"] != previous.get("mode"):
            return {
                "change_type": "permission_changed",
                "occurred_at": utcnow_iso(),
                "sha256": record["sha256"],
                "size": record["size"],
            }
        return None

    def _record_history(
        self,
        history: list[dict[str, Any]],
        change: dict[str, Any],
        previous: dict[str, Any] | None,
        record: dict[str, Any] | None,
    ) -> None:
        before = previous.get("sha256") if previous else None
        after = record["sha256"] if record else change.get("sha256")
        history.append(
            {
                "event_id": change["event_id"],
                "path": change["path"],
                "change_type": change["change_type"],
                "occurred_at": change["occurred_at"],
                "before_sha256": before,
                "after_sha256": after,
                "size": change.get("size"),
            }
        )

    @staticmethod
    def _load_dict(path: Path) -> dict[str, dict[str, Any]]:
        if not Path(path).exists():
            return {}
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _load_list(path: Path) -> list[dict[str, Any]]:
        if not Path(path).exists():
            return []
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            return raw if isinstance(raw, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    @staticmethod
    def _save_json(path: Path, obj: Any) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(obj, sort_keys=True), encoding="utf-8")
        temp.replace(path)


# -- Windows event log -----------------------------------------------------


class WindowsEventLogSource:
    """Reads recent events from Windows event log channels via wevtapi.

    One or more channels (``System``, ``Security``, ...) are queried; a channel
    that cannot be opened (missing privilege, service error) is logged and the
    remaining channels are still read. When every channel fails the adapter
    reports an explicit ``unavailable`` outcome with the combined reasons --
    never a silent empty result.
    """

    name = "events.windows.eventlog"

    _EVT_QUERY_CHANNEL_PATH = 0x1
    _EVT_RENDER_EVENT_XML = 1
    _ERROR_INSUFFICIENT_BUFFER = 122
    _ERROR_NO_MORE_ITEMS = 259
    _EVT_NS = "{http://schemas.microsoft.com/win/2004/08/events/event}"
    #: Hard cap on records drained per query to bound per-cycle work.
    _DRAIN_LIMIT = 2000

    def __init__(
        self,
        channel: str | None = None,
        *,
        channels: tuple[str, ...] | None = None,
        max_events: int = 50,
    ) -> None:
        if channels:
            self._channels = tuple(channels)
        elif channel:
            self._channels = (channel,)
        else:
            self._channels = ("System",)
        self._max_events = max_events
        self._lib: Any = None

    @property
    def channels(self) -> tuple[str, ...]:
        return self._channels

    def set_channels(self, channels: tuple[str, ...]) -> None:
        """Replace the queried channels (used by policy application)."""
        if channels:
            self._channels = tuple(channels)

    def _load_lib(self) -> Any:
        if self._lib is not None:
            return self._lib
        if os.name != "nt":
            raise OSError("Windows event log requires Windows")
        lib = ctypes.WinDLL("wevtapi", use_last_error=True)
        lib.EvtQuery.argtypes = [
            wintypes.HANDLE,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
        ]
        lib.EvtQuery.restype = wintypes.HANDLE
        lib.EvtNext.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        lib.EvtNext.restype = wintypes.BOOL
        lib.EvtRender.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
        lib.EvtRender.restype = wintypes.BOOL
        lib.EvtClose.argtypes = [wintypes.HANDLE]
        lib.EvtClose.restype = wintypes.BOOL
        self._lib = lib
        return lib

    def collect_events(self, since: datetime) -> AdapterOutcome:
        try:
            lib = self._load_lib()
        except OSError as exc:
            return AdapterOutcome.unavailable(str(exc))
        since_iso = _iso(since)
        events: list[dict[str, Any]] = []
        failures: list[str] = []
        for channel in self._channels:
            # Time-filtered XPath (no reverse-direction flag): reliable on all
            # Windows builds and bounds the result set to the requested window.
            query_text = f"Event/System/TimeCreated[@SystemTime>='{since_iso}']"
            query = lib.EvtQuery(None, channel, query_text, self._EVT_QUERY_CHANNEL_PATH)
            if not query:
                error = ctypes.get_last_error()
                failures.append(f"{channel}: EvtQuery failed ({error})")
                continue
            try:
                events.extend(self._drain(lib, query, self._DRAIN_LIMIT))
            finally:
                lib.EvtClose(query)
        if failures:
            logger.warning("windows event log channel errors: %s", "; ".join(failures))
        if not events and len(failures) == len(self._channels):
            return AdapterOutcome.unavailable(f"all event channels failed: {'; '.join(failures)}")
        # Records arrive oldest-first; keep only the most recent ``max_events``.
        events.sort(key=lambda item: item["occurred_at"], reverse=True)
        return AdapterOutcome.ok(events[: self._max_events])

    def _drain(self, lib: Any, query: int, limit: int) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        while len(events) < limit:
            batch_size = min(64, limit - len(events))
            handles = (wintypes.HANDLE * batch_size)()
            returned = wintypes.DWORD(0)
            ok = lib.EvtNext(
                query,
                batch_size,
                handles,
                1000,
                0,
                ctypes.byref(returned),
            )
            if not ok and ctypes.get_last_error() == self._ERROR_NO_MORE_ITEMS:
                break
            if not ok:
                break
            try:
                for handle in handles[: returned.value]:
                    event = self._render_event(lib, cast(int, handle))
                    if event is not None:
                        events.append(event)
            finally:
                for handle in handles[: returned.value]:
                    lib.EvtClose(handle)
        return events

    def _render_event(self, lib: Any, handle: int) -> dict[str, Any] | None:
        xml_text = self._render_xml(lib, handle)
        if xml_text is None:
            return None
        try:
            # The XML comes from the local Windows Event Log service (trusted
            # system data), so stdlib ElementTree is safe here.
            root = ET.fromstring(xml_text)  # noqa: S314 -- trusted local system input
        except ET.ParseError:
            return None
        system = root.find(f"{self._EVT_NS}System")
        if system is None:
            return None
        time_element = system.find(f"{self._EVT_NS}TimeCreated")
        occurred_at = (
            _normalize_xml_time(time_element.get("SystemTime"))
            if time_element is not None
            else None
        )
        if occurred_at is None:
            return None
        provider_element = system.find(f"{self._EVT_NS}Provider")
        provider = (
            provider_element.get("Name") if provider_element is not None else None
        ) or "Unknown"
        event_id_text = system.findtext(f"{self._EVT_NS}EventID")
        record_id = system.findtext(f"{self._EVT_NS}EventRecordID") or event_id_text or "0"
        channel_name = system.findtext(f"{self._EVT_NS}Channel") or "unknown"
        severity = _map_event_level(_as_int_text(system.findtext(f"{self._EVT_NS}Level")))
        summary = f"[{channel_name}] EventID {event_id_text or '?'} from {provider}"
        return {
            "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"hg:{channel_name}:{record_id}")),
            "event_type": f"windows.event.{provider}"[:64],
            "occurred_at": occurred_at,
            "severity": severity,
            "summary": summary[:1024],
            "source_ip": None,
            "username": None,
            "metadata": _extract_event_data(root),
        }

    def _render_xml(self, lib: Any, handle: int) -> str | None:
        used = wintypes.DWORD(0)
        count = wintypes.DWORD(0)
        size = 64 * 1024
        buffer = ctypes.create_string_buffer(size)
        ok = lib.EvtRender(
            None,
            handle,
            self._EVT_RENDER_EVENT_XML,
            size,
            ctypes.cast(buffer, ctypes.c_void_p),
            ctypes.byref(used),
            ctypes.byref(count),
        )
        if not ok and ctypes.get_last_error() == self._ERROR_INSUFFICIENT_BUFFER:
            size = int(used.value)
            buffer = ctypes.create_string_buffer(size)
            ok = lib.EvtRender(
                None,
                handle,
                self._EVT_RENDER_EVENT_XML,
                size,
                ctypes.cast(buffer, ctypes.c_void_p),
                ctypes.byref(used),
                ctypes.byref(count),
            )
        if not ok:
            return None
        # EvtRender writes UTF-16LE with a NUL terminator. ``.value`` would
        # stop at the first NUL high byte, so slice the raw region by the
        # reported size, then trim the single trailing NUL character.
        raw = buffer.raw[: int(used.value)]
        return raw.decode("utf-16-le", errors="replace").rstrip("\x00")


# -- Linux journald ---------------------------------------------------------


class LinuxJournaldEventSource:
    """Reads security-relevant journald records via ``journalctl --output=json``.

    The ``journalctl`` binary is invoked with the list-arg form (no shell), so
    record payloads are never interpreted by a shell. When the binary is
    missing, exits non-zero (permission denied) or the host is not Linux the
    adapter returns an explicit ``unavailable`` outcome.
    """

    name = "events.linux.journald"

    def __init__(
        self,
        *,
        max_events: int = 50,
        runner: Callable[[list[str]], tuple[int, str, str]] | None = None,
        journalctl: str = "journalctl",
        timeout: int = 30,
    ) -> None:
        self._max_events = max_events
        self._runner = runner or self._default_runner
        self._journalctl = journalctl
        self._timeout = timeout

    @staticmethod
    def _default_runner(args: list[str]) -> tuple[int, str, str]:
        result = subprocess.run(  # noqa: S603, S607 -- list-arg invocation, trusted binary
            args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout, result.stderr

    def collect_events(self, since: datetime) -> AdapterOutcome:
        if not sys.platform.startswith("linux"):
            return AdapterOutcome.unavailable("journald collection requires Linux")
        since_iso = _iso(since)
        args = [self._journalctl, "--since", since_iso, "--output=json", "--no-pager"]
        try:
            returncode, stdout, stderr = self._runner(args)
        except (OSError, subprocess.SubprocessError) as exc:
            return AdapterOutcome.unavailable(f"journalctl unavailable: {exc}")
        if returncode != 0:
            reason = (stderr or stdout or "").strip()[:200]
            return AdapterOutcome.unavailable(f"journalctl failed ({returncode}): {reason}")
        events: list[dict[str, Any]] = []
        for line in stdout.splitlines():
            if len(events) >= self._max_events:
                break
            try:
                record = json.loads(line)
            except (ValueError, json.JSONDecodeError):
                continue
            event = self._map_record(record)
            if event is not None:
                events.append(event)
        return AdapterOutcome.ok(events)

    def _map_record(self, record: dict[str, Any]) -> dict[str, Any] | None:
        message = str(record.get("MESSAGE") or "").strip()
        if not message:
            return None
        occurred_at = _journal_timestamp(record.get("__REALTIME_TIMESTAMP")) or utcnow_iso()
        cursor = record.get("__CURSOR") or f"journal:{occurred_at}:{record.get('_PID', '0')}"
        unit = record.get("_SYSTEMD_UNIT") or record.get("_UNIT") or "unknown"
        return {
            "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"hg:journal:{cursor}")),
            "event_type": f"linux.journal.{unit}"[:64],
            "occurred_at": occurred_at,
            "severity": _map_journal_priority(_as_int_text(str(record.get("PRIORITY")) or "6")),
            "summary": message[:1024],
            "source_ip": None,
            "username": str(record["_UID"]) if record.get("_UID") is not None else None,
            "metadata": {
                key: str(record[key])[:256]
                for key in ("_PID", "_TRANSPORT", "_HOSTNAME", "_SOURCE_REALTIME_TIMESTAMP")
                if key in record
            },
        }


def _journal_timestamp(value: str | None) -> str | None:
    """Convert a journald microsecond epoch to a UTC ISO-8601 ``Z`` string."""
    if not value:
        return None
    try:
        return _iso(datetime.fromtimestamp(int(value) / 1_000_000, tz=UTC))
    except (ValueError, OverflowError):
        return None


def _map_journal_priority(priority: int) -> str:
    # syslog priorities: 0 emerg, 1 alert, 2 crit, 3 err, 4 warning, 5 notice, 6 info, 7 debug
    if priority <= 2:
        return "critical"
    if priority == 3:
        return "high"
    if priority <= 5:
        return "medium"
    return "low"


# -- factories --------------------------------------------------------------


def default_event_source() -> EventSource:
    """The event source for the current platform."""
    if os.name == "nt":
        return WindowsEventLogSource(channels=("System", "Security"))
    if sys.platform.startswith("linux"):
        return LinuxJournaldEventSource()
    return UnavailableEventSource(
        "event log collection is only implemented for Windows and Linux"
    )


def default_baseline_provider() -> BaselineProvider:
    return BasicHardeningBaseline()


def default_fim_provider(data_dir: Path, watch_dirs: tuple[str, ...] = ()) -> FIMProvider:
    if watch_dirs:
        return DirectoryFIMProvider(data_dir, watch_dirs)
    return UnavailableFIMProvider("no FIM watch directories configured")


# -- helpers -----------------------------------------------------------------


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _normalize_xml_time(value: str | None) -> str | None:
    if not value:
        return None
    # Windows SystemTime may carry 7 fractional digits, which datetime cannot
    # parse; truncate to microseconds before conversion.
    if "." in value:
        head, _, tail = value.partition(".")
        fraction = tail.rstrip("Z")[:6]
        value = f"{head}.{fraction}Z"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def _map_event_level(level: int) -> str:
    if level == 1:
        return "critical"
    if level == 2:
        return "high"
    if level == 3:
        return "medium"
    return "low"


def _as_int_text(value: str | None) -> int:
    try:
        return int(value or "0")
    except ValueError:
        return 0


def _extract_event_data(root: ET.Element) -> dict[str, Any]:
    """Flatten EventData pairs (limited to 32 keys for schema compliance)."""
    data: dict[str, Any] = {}
    for elem in root.iter():
        if not elem.tag.endswith("Data") or elem.text is None or not elem.text.strip():
            continue
        key = elem.get("Name") or f"value{len(data)}"
        data[key] = elem.text.strip()
        if len(data) >= 32:
            break
    return data
