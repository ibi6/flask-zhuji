"""Inventory baseline scanning and drift detection.

The :class:`InventoryBaselineProvider` builds an :class:`InventorySnapshot`
covering system identity, installed services, software, startup items and
listening ports, stores it as the host baseline and diffs every later scan
against it. Drift is reported as schema-compatible ``baseline_results`` with
``pass`` / ``fail`` / ``unavailable`` status.

Each subsystem collector is individually guarded: a subsystem that cannot be
queried (missing package manager, missing privilege) yields an explicit
``unavailable`` check with the concrete reason instead of being silently
skipped.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import socket
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__
from .adapters import AdapterOutcome

logger = logging.getLogger(__name__)

__all__ = [
    "InventorySnapshot",
    "BaselineResult",
    "InventoryBaselineProvider",
    "default_inventory_collectors",
]

#: A collector returns ``(items, error_reason)``; ``error_reason`` is ``None``
#: on success and otherwise explains why the subsystem could not be read.
SectionCollector = Callable[[], tuple[list[dict[str, Any]], str | None]]


@dataclass(frozen=True)
class InventorySnapshot:
    """A point-in-time view of the host used for baseline drift detection."""

    collected_at: str
    system: dict[str, Any]
    services: list[dict[str, Any]]
    software: list[dict[str, Any]]
    startup_items: list[dict[str, Any]]
    listening_ports: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "collected_at": self.collected_at,
            "system": self.system,
            "services": self.services,
            "software": self.software,
            "startup_items": self.startup_items,
            "listening_ports": self.listening_ports,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> InventorySnapshot:
        return cls(
            collected_at=str(raw.get("collected_at") or ""),
            system=dict(raw.get("system") or {}),
            services=list(raw.get("services") or []),
            software=list(raw.get("software") or []),
            startup_items=list(raw.get("startup_items") or []),
            listening_ports=list(raw.get("listening_ports") or []),
        )


@dataclass(frozen=True)
class BaselineResult:
    """A single schema-compatible baseline check result."""

    check_id: str
    status: str
    checked_at: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id[:64],
            "status": self.status,
            "checked_at": self.checked_at,
            "message": self.message[:1024],
        }


class InventoryBaselineProvider:
    """Builds, stores and diffs the host inventory baseline."""

    name = "baseline.inventory"

    def __init__(
        self,
        data_dir: Path,
        *,
        collectors: dict[str, SectionCollector] | None = None,
    ) -> None:
        self._path = Path(data_dir) / "baseline_inventory.json"
        self._collectors = collectors if collectors is not None else default_inventory_collectors()

    def collect_baseline(self, checked_at: datetime) -> AdapterOutcome:
        """Return baseline checks; the first call establishes the baseline."""
        checked = _iso(checked_at)
        sections = self._gather()
        current = InventorySnapshot(
            collected_at=checked,
            system=sections["system"][0],
            services=sections["services"][0],
            software=sections["software"][0],
            startup_items=sections["startup_items"][0],
            listening_ports=sections["listening_ports"][0],
        )
        previous = self._load()
        if previous is None:
            self._save(current)
            message = (
                f"baseline established: {len(current.services)} services, "
                f"{len(current.software)} software, "
                f"{len(current.startup_items)} startup items, "
                f"{len(current.listening_ports)} listening ports"
            )
            return AdapterOutcome.ok(
                [BaselineResult("baseline.established", "pass", checked, message).as_dict()]
            )
        results = self._diff(previous, current, sections, checked)
        self._save(current)
        return AdapterOutcome.ok([result.as_dict() for result in results])

    def _gather(self) -> dict[str, tuple[Any, str | None]]:
        sections: dict[str, tuple[Any, str | None]] = {
            "system": (_collect_system(), None)
        }
        for name, collector in self._collectors.items():
            try:
                items, error = collector()
            except Exception as exc:  # noqa: BLE001 -- isolation boundary per subsystem
                logger.warning("baseline section %s failed: %s", name, exc)
                items, error = [], str(exc)
            sections[name] = (list(items or []), error)
        return sections

    def _diff(
        self,
        previous: InventorySnapshot,
        current: InventorySnapshot,
        sections: dict[str, tuple[Any, str | None]],
        checked: str,
    ) -> list[BaselineResult]:
        results: list[BaselineResult] = []

        if previous.system.get("hostname") != current.system.get("hostname"):
            results.append(
                BaselineResult(
                    "baseline.system",
                    "fail",
                    checked,
                    f"hostname changed from {previous.system.get('hostname')!r} "
                    f"to {current.system.get('hostname')!r}",
                )
            )
        elif previous.system.get("os") != current.system.get("os"):
            results.append(
                BaselineResult(
                    "baseline.system",
                    "fail",
                    checked,
                    f"operating system changed from {previous.system.get('os')!r} "
                    f"to {current.system.get('os')!r}",
                )
            )
        else:
            results.append(
                BaselineResult("baseline.system", "pass", checked, "system identity unchanged")
            )

        section_specs = (
            ("services", "services"),
            ("software", "installed software"),
            ("startup_items", "startup items"),
            ("listening_ports", "listening ports"),
        )
        for name, label in section_specs:
            items, error = sections[name]
            if error:
                results.append(
                    BaselineResult(
                        f"baseline.{name}",
                        "unavailable",
                        checked,
                        f"cannot collect {label}: {error[:200]}",
                    )
                )
                continue
            current_values = getattr(current, name)
            previous_values = getattr(previous, name)
            diff_message = _diff_section(name, previous_values, current_values)
            if diff_message is None:
                results.append(
                    BaselineResult(f"baseline.{name}", "pass", checked, f"{label} unchanged")
                )
            else:
                results.append(
                    BaselineResult(f"baseline.{name}", "fail", checked, diff_message)
                )
        return results

    def _load(self) -> InventorySnapshot | None:
        if not self._path.exists():
            return None
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return InventorySnapshot.from_dict(raw) if isinstance(raw, dict) else None
        except (OSError, json.JSONDecodeError, ValueError):
            logger.warning("ignoring unreadable baseline snapshot at %s", self._path)
            return None

    def _save(self, snapshot: InventorySnapshot) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix(self._path.suffix + ".tmp")
        temp.write_text(json.dumps(snapshot.as_dict(), sort_keys=True), encoding="utf-8")
        temp.replace(self._path)


def _diff_section(
    name: str,
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> str | None:
    """Return a human-readable drift message, or ``None`` when unchanged."""
    previous_keys = {_section_key(name, record) for record in previous}
    current_keys = {_section_key(name, record) for record in current}
    if previous_keys == current_keys:
        return None
    added = sorted(str(k) for k in current_keys - previous_keys)
    removed = sorted(str(k) for k in previous_keys - current_keys)
    parts: list[str] = []
    if added:
        parts.append(f"added {len(added)}: {', '.join(added[:5])}")
    if removed:
        parts.append(f"removed {len(removed)}: {', '.join(removed[:5])}")
    return "; ".join(parts)


def _section_key(name: str, record: dict[str, Any]) -> tuple[Any, ...]:
    """Stable identity key for a baseline record in a given section."""
    if name == "listening_ports":
        return (record.get("protocol"), record.get("local_address"), record.get("local_port"))
    if name == "services":
        return (record.get("name"), record.get("state"))
    if name == "software":
        return (record.get("name"), record.get("version"))
    return (record.get("name"), record.get("command"))


def _collect_system() -> dict[str, Any]:
    system = platform.system().lower()
    if system.startswith("windows"):
        os_name = "windows"
    elif system == "linux":
        os_name = "linux"
    else:
        os_name = system
    return {
        "hostname": socket.gethostname()[:255] or "unknown",
        "os": os_name,
        "os_version": platform.platform()[:255],
        "architecture": platform.machine()[:64],
        "agent_version": __version__[:32],
        "boot_time": _boot_time(),
    }


def _boot_time() -> str | None:
    try:
        import psutil

        return _iso(datetime.fromtimestamp(float(psutil.boot_time()), tz=UTC))
    except (OSError, ImportError, ValueError):
        return None


def default_inventory_collectors() -> dict[str, SectionCollector]:
    """Platform-appropriate collectors, each guarded and self-explanatory."""
    return {
        "services": _collect_services,
        "software": _collect_software,
        "startup_items": _collect_startup_items,
        "listening_ports": _collect_ports,
    }


# -- subsystem collectors ----------------------------------------------------


def _run_cmd(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """Run a trusted command with list arguments (no shell involved)."""
    # ``errors="replace"`` keeps Windows OEM-codepage output (e.g. Chinese
    # ``sc query``) from crashing the decode thread; non-ASCII payloads become
    # replacement characters instead of failing the whole section.
    return subprocess.run(  # noqa: S603, S607 -- list-arg invocation, trusted binary
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _collect_services() -> tuple[list[dict[str, Any]], str | None]:
    if sys.platform.startswith("win"):
        return _windows_services()
    if sys.platform.startswith("linux"):
        return _linux_services()
    return [], "service enumeration is not implemented on this platform"


def _windows_services() -> tuple[list[dict[str, Any]], str | None]:
    try:
        result = _run_cmd(["sc", "query", "type=", "service", "state=", "all"], timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return [], f"sc query failed: {exc}"
    if result.returncode != 0:
        return [], f"sc query exited with {result.returncode}"
    services: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for line in result.stdout.splitlines():
        text = line.strip()
        if text.startswith("SERVICE_NAME:"):
            current = {"name": text.split(":", 1)[1].strip()}
        elif "STATE" in text:
            parts = text.split(":", 1)[1].split()
            current["state"] = parts[-1] if parts else "unknown"
            services.append(current)
        elif "START_TYPE" in text and current:
            parts = text.split(":", 1)[1].split()
            current["start_type"] = parts[-1] if parts else "unknown"
    return services, None


def _linux_services() -> tuple[list[dict[str, Any]], str | None]:
    try:
        result = _run_cmd(
            ["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--no-pager"],
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [], f"systemctl failed: {exc}"
    if result.returncode != 0:
        return [], f"systemctl exited with {result.returncode}"
    services: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        services.append({"name": parts[0], "state": parts[2], "start_type": parts[1]})
    return services, None


def _collect_software() -> tuple[list[dict[str, Any]], str | None]:
    if sys.platform.startswith("win"):
        return _windows_software()
    if sys.platform.startswith("linux"):
        return _linux_software()
    return [], "software inventory is not implemented on this platform"


def _windows_software() -> tuple[list[dict[str, Any]], str | None]:
    try:
        import winreg
    except ImportError as exc:  # pragma: no cover -- Windows-only import
        return [], f"winreg unavailable: {exc}"
    roots = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    software: list[dict[str, Any]] = []
    for root in roots:
        try:
            parent = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root)
        except OSError:
            continue
        try:
            count = winreg.QueryInfoKey(parent)[0]
            for index in range(count):
                try:
                    sub_key = winreg.OpenKey(parent, winreg.EnumKey(parent, index))
                except OSError:
                    continue
                try:
                    name = _reg_value(sub_key, "DisplayName")
                    if not name:
                        continue
                    software.append(
                        {
                            "name": name,
                            "version": _reg_value(sub_key, "DisplayVersion"),
                            "vendor": _reg_value(sub_key, "Publisher"),
                        }
                    )
                finally:
                    sub_key.Close()
        finally:
            parent.Close()
    return software, None


def _reg_value(key: Any, name: str) -> str | None:
    import winreg  # pragma: no cover -- only called on Windows

    try:
        value = winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None
    return str(value) if value else None


def _linux_software() -> tuple[list[dict[str, Any]], str | None]:
    candidates: list[tuple[list[str], str]] = [
        (["dpkg-query", "-W", "-f=${Package}\t${Version}\n"], "dpkg"),
        (["rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}\n"], "rpm"),
    ]
    for args, _kind in candidates:
        try:
            result = _run_cmd(args, timeout=60)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode != 0:
            continue
        items: list[dict[str, Any]] = []
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if not parts or not parts[0]:
                continue
            items.append({"name": parts[0], "version": parts[1] if len(parts) > 1 else None})
        return items, None
    return [], "no supported package manager found (dpkg/rpm missing or failed)"


def _collect_startup_items() -> tuple[list[dict[str, Any]], str | None]:
    if sys.platform.startswith("win"):
        return _windows_startup_items()
    if sys.platform.startswith("linux"):
        return _linux_startup_items()
    return [], "startup item enumeration is not implemented on this platform"


def _windows_startup_items() -> tuple[list[dict[str, Any]], str | None]:
    try:
        import winreg
    except ImportError as exc:  # pragma: no cover -- Windows-only import
        return [], f"winreg unavailable: {exc}"
    items: list[dict[str, Any]] = []
    run_roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    ]
    for hive, path in run_roots:
        try:
            key = winreg.OpenKey(hive, path)
        except OSError:
            continue
        try:
            count = winreg.QueryInfoKey(key)[1]  # value count
            for index in range(count):
                name, value, _ = winreg.EnumValue(key, index)
                items.append({"name": name, "command": str(value)})
        finally:
            key.Close()
    for folder in (
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup",
    ):
        if not folder.is_dir():
            continue
        for child in sorted(folder.iterdir()):
            if child.is_file():
                items.append({"name": child.name, "command": str(child)})
    return items, None


def _linux_startup_items() -> tuple[list[dict[str, Any]], str | None]:
    try:
        result = _run_cmd(
            [
                "systemctl",
                "list-unit-files",
                "--type=service",
                "--state=enabled",
                "--no-legend",
                "--no-pager",
            ],
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [], f"systemctl failed: {exc}"
    if result.returncode != 0:
        return [], f"systemctl exited with {result.returncode}"
    items: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        name = line.split()[0] if line.split() else ""
        if name:
            items.append({"name": name, "command": name})
    return items, None


def _collect_ports() -> tuple[list[dict[str, Any]], str | None]:
    try:
        import psutil
    except ImportError as exc:
        return [], f"psutil unavailable: {exc}"
    ports: list[dict[str, Any]] = []
    for kind in ("tcp", "udp"):
        try:
            connections = psutil.net_connections(kind=kind)
        except (psutil.AccessDenied, psutil.Error):
            continue
        for conn in connections:
            laddr = getattr(conn, "laddr", None)
            if laddr is None or not getattr(laddr, "ip", None):
                continue
            if kind == "tcp" and getattr(conn, "status", None) != "LISTEN":
                continue
            ports.append(
                {
                    "protocol": kind,
                    "local_address": laddr.ip[:64],
                    "local_port": int(laddr.port),
                    "pid": getattr(conn, "pid", None),
                }
            )
    return ports, None


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
