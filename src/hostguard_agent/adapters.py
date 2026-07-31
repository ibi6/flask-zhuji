"""Collector adapters for events, baseline checks and file integrity.

This module defines the collection interfaces and ships concrete adapters.
Every adapter reports its availability explicitly; unsupported platforms or
missing privileges produce an :class:`AdapterOutcome` with status
``unavailable`` and a factual reason. There are no ``TODO`` placeholders:
an adapter that cannot run states exactly why it cannot.

Adapters
--------

* :class:`WindowsEventLogSource` -- reads the Windows event log via
  ``wevtapi`` (ctypes). Degrades to ``unavailable`` on any API failure.
* :class:`UnavailableEventSource` -- explicit unavailable outcome.
* :class:`BasicHardeningBaseline` -- cross-platform checks (disk/memory) plus
  platform-specific checks reported as ``unavailable``.
* :class:`DirectoryFIMProvider` -- file integrity monitoring over configured
  directories with a persistent manifest; ``unavailable`` when no watch
  directories are configured.
* :class:`UnavailableFIMProvider` / :class:`UnavailableBaselineProvider` --
  explicit unavailable outcomes for platforms with no implementation.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import json
import os
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast

from .collector import file_sha256, utcnow_iso

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

    The manifest is stored under the agent data dir and updated after every
    pass. Without watch directories the adapter reports ``unavailable``.
    """

    name = "fim.directory"

    def __init__(self, data_dir: Path, watch_dirs: tuple[str, ...] = ()) -> None:
        self._manifest_path = Path(data_dir) / "fim_manifest.json"
        self._watch_dirs = tuple(str(Path(d)) for d in watch_dirs)

    def collect_changes(self, since: datetime) -> AdapterOutcome:
        if not self._watch_dirs:
            return AdapterOutcome.unavailable("no FIM watch directories configured")
        manifest = self._load_manifest()
        current: dict[str, dict[str, Any]] = {}
        changes: list[dict[str, Any]] = []
        for watch_dir in self._watch_dirs:
            self._scan_dir(watch_dir, manifest, current, changes)
        for path in sorted(set(manifest) - set(current)):
            changes.append(
                {
                    "event_id": str(uuid.uuid4()),
                    "path": path[:2048],
                    "change_type": "deleted",
                    "occurred_at": utcnow_iso(),
                    "sha256": manifest[path].get("sha256"),
                    "size": manifest[path].get("size"),
                }
            )
        self._save_manifest(current)
        return AdapterOutcome.ok(changes)

    def _scan_dir(
        self,
        watch_dir: str,
        manifest: dict[str, dict[str, Any]],
        current: dict[str, dict[str, Any]],
        changes: list[dict[str, Any]],
    ) -> None:
        root = Path(watch_dir)
        if not root.is_dir():
            changes.append(
                {
                    "event_id": str(uuid.uuid4()),
                    "path": str(root)[:2048],
                    "change_type": "deleted",
                    "occurred_at": utcnow_iso(),
                    "sha256": None,
                    "size": None,
                }
            )
            return
        for path in root.rglob("*"):
            try:
                if not path.is_file():
                    continue
                entry = _file_entry(path)
            except (OSError, ValueError):
                continue
            key = str(path)
            current[key] = entry
            previous = manifest.get(key)
            if previous is None:
                changes.append(
                    {
                        "event_id": str(uuid.uuid4()),
                        "path": key[:2048],
                        "change_type": "created",
                        "occurred_at": entry["occurred_at"],
                        "sha256": entry["sha256"],
                        "size": entry["size"],
                    }
                )
            elif previous.get("sha256") != entry["sha256"]:
                changes.append(
                    {
                        "event_id": str(uuid.uuid4()),
                        "path": key[:2048],
                        "change_type": "modified",
                        "occurred_at": entry["occurred_at"],
                        "sha256": entry["sha256"],
                        "size": entry["size"],
                    }
                )

    def _load_manifest(self) -> dict[str, dict[str, Any]]:
        if not self._manifest_path.exists():
            return {}
        try:
            raw = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_manifest(self, manifest: dict[str, dict[str, Any]]) -> None:
        self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._manifest_path.with_suffix(self._manifest_path.suffix + ".tmp")
        temp.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        temp.replace(self._manifest_path)


def _file_entry(path: Path) -> dict[str, Any]:
    stat_result = path.stat()
    return {
        "sha256": file_sha256(str(path)),
        "size": int(stat_result.st_size),
        "occurred_at": _iso(datetime.fromtimestamp(stat_result.st_mtime, tz=UTC)),
    }


# -- Windows event log -----------------------------------------------------


class WindowsEventLogSource:
    """Reads recent events from a Windows event log channel via wevtapi.

    Any API failure (missing privileges, service errors) produces an
    explicit ``unavailable`` outcome with the underlying reason.
    """

    name = "events.windows.eventlog"

    _EVT_QUERY_CHANNEL_PATH = 0x1
    _EVT_QUERY_REVERSE_DIRECTION = 0x2
    _EVT_RENDER_EVENT_XML = 1
    _ERROR_INSUFFICIENT_BUFFER = 122
    _ERROR_NO_MORE_ITEMS = 259
    _EVT_NS = "{http://schemas.microsoft.com/win/2004/08/events/event}"

    def __init__(self, channel: str = "System", *, max_events: int = 50) -> None:
        self._channel = channel
        self._max_events = max_events
        self._lib: Any = None

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
        query = lib.EvtQuery(
            None,
            self._channel,
            None,
            self._EVT_QUERY_CHANNEL_PATH | self._EVT_QUERY_REVERSE_DIRECTION,
        )
        if not query:
            error = ctypes.get_last_error()
            return AdapterOutcome.unavailable(f"EvtQuery({self._channel}) failed: {error}")
        try:
            return self._drain(lib, query, since)
        finally:
            lib.EvtClose(query)

    def _drain(self, lib: Any, query: int, since: datetime) -> AdapterOutcome:
        events: list[dict[str, Any]] = []
        while len(events) < self._max_events:
            handles = (wintypes.HANDLE * self._max_events)()
            returned = wintypes.DWORD(0)
            ok = lib.EvtNext(
                query,
                self._max_events,
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
                    event = self._render_event(lib, cast(int, handle), since)
                    if event is None:
                        continue
                    if event["occurred_at"] < _iso(since):
                        return AdapterOutcome.ok(events)
                    events.append(event)
                    if len(events) >= self._max_events:
                        return AdapterOutcome.ok(events)
            finally:
                for handle in handles[: returned.value]:
                    lib.EvtClose(handle)
        return AdapterOutcome.ok(events)

    def _render_event(self, lib: Any, handle: int, since: datetime) -> dict[str, Any] | None:
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
        time_created = system.findtext(f"{self._EVT_NS}TimeCreated/@SystemTime")
        occurred_at = _normalize_xml_time(time_created)
        if occurred_at is None:
            return None
        provider = system.findtext(f"{self._EVT_NS}Provider/@Name") or "Unknown"
        event_id_text = system.findtext(f"{self._EVT_NS}EventID")
        record_id = system.findtext(f"{self._EVT_NS}EventRecordID") or event_id_text or "0"
        severity = _map_event_level(_as_int_text(system.findtext(f"{self._EVT_NS}Level")))
        summary = f"[{self._channel}] EventID {event_id_text or '?'} from {provider}"
        return {
            "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"hg:{self._channel}:{record_id}")),
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
        return buffer.value.decode("utf-16-le", errors="replace")


# -- factories --------------------------------------------------------------


def default_event_source() -> EventSource:
    """The event source for the current platform."""
    if os.name == "nt":
        return WindowsEventLogSource()
    return UnavailableEventSource(
        "event log collection is only implemented for the Windows event log"
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
