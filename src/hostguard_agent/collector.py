"""Cross-platform system telemetry collection backed by psutil.

Produces schema-compatible sections (see ``contracts/telemetry.schema.json``):

* ``metrics`` -- CPU, memory, disk and network utilization.
* ``inventory`` -- host identity, refreshed occasionally.
* ``processes`` -- light-weight process summaries. Full command lines and
  environment variables are deliberately NOT collected.
* ``listening_ports`` -- TCP/UDP listening endpoints.

All timestamps are UTC ISO-8601 with a trailing ``Z``. Collection failures
for individual processes or sections degrade gracefully: access-denied
processes appear with ``None`` detail fields and unsupported sections are
omitted rather than raised.
"""

from __future__ import annotations

import hashlib
import platform
import socket
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import psutil

from . import __version__

__all__ = [
    "SystemCollector",
    "build_batch",
    "utcnow_iso",
    "PROCESS_LIMIT",
    "PORT_LIMIT",
]

PROCESS_LIMIT = 2000
PORT_LIMIT = 2000
INVENTORY_IP_LIMIT = 32


def utcnow_iso() -> str:
    """Current UTC time as ISO-8601 with a trailing ``Z``."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _iso_from_epoch(value: float | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=UTC).isoformat().replace("+00:00", "Z")


class SystemCollector:
    """Collects host telemetry; every callable is individually guarded."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        agent_version: str = __version__,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._agent_version = agent_version

    def _now_iso(self) -> str:
        return self._clock().astimezone(UTC).isoformat().replace("+00:00", "Z")

    # -- individual sections ----------------------------------------------

    def collect_metrics(self) -> dict[str, Any]:
        """CPU/memory/disk/network utilization for the required metrics block."""
        try:
            disk = psutil.disk_usage("/")
            disk_percent = float(disk.percent)
        except (OSError, psutil.Error):
            disk_percent = 0.0
        try:
            net = psutil.net_io_counters()
            bytes_sent, bytes_recv = int(net.bytes_sent), int(net.bytes_recv)
        except (OSError, psutil.Error):
            bytes_sent, bytes_recv = 0, 0
        try:
            memory_percent = float(psutil.virtual_memory().percent)
        except (OSError, psutil.Error):
            memory_percent = 0.0
        try:
            cpu_percent = float(psutil.cpu_percent(interval=None))
        except (OSError, psutil.Error):
            cpu_percent = 0.0
        return {
            "cpu_percent": _clamp_percent(cpu_percent),
            "memory_percent": _clamp_percent(memory_percent),
            "disk_percent": _clamp_percent(disk_percent),
            "network_bytes_sent": bytes_sent,
            "network_bytes_recv": bytes_recv,
        }

    def collect_inventory(self) -> dict[str, Any]:
        """Host identity used by the inventory block."""
        system = platform.system().lower()
        if system.startswith("windows"):
            os_name = "windows"
        elif system == "linux":
            os_name = "linux"
        else:
            os_name = system
        boot_time: str | None = None
        try:
            boot_time = _iso_from_epoch(float(psutil.boot_time()))
        except (OSError, psutil.Error, ValueError):
            boot_time = None
        return {
            "hostname": socket.gethostname()[:255] or "unknown",
            "os": os_name,
            "os_version": platform.platform()[:255],
            "architecture": platform.machine()[:64],
            "agent_version": self._agent_version[:32],
            "boot_time": boot_time,
            "ip_addresses": _ip_addresses(),
        }

    def collect_processes(self) -> list[dict[str, Any]]:
        """Summaries of running processes without command lines or env vars."""
        processes: list[dict[str, Any]] = []
        try:
            iterator = psutil.process_iter(attrs=["pid", "name", "exe", "username", "create_time"])
            for proc in iterator:
                if len(processes) >= PROCESS_LIMIT:
                    break
                try:
                    info = proc.info
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                processes.append(
                    {
                        "pid": _as_int(info.get("pid")),
                        "name": str(info.get("name") or "unknown")[:255],
                        "executable": _optional_str(info.get("exe"), 1024),
                        "username": _optional_str(info.get("username"), 255),
                        "started_at": _iso_from_epoch(_as_float(info.get("create_time"))),
                    }
                )
        except psutil.Error:
            # psutil fully unavailable for process iteration.
            pass
        return processes

    def collect_listening_ports(self) -> list[dict[str, Any]]:
        """TCP/UDP endpoints in the listening state."""
        ports: list[dict[str, Any]] = []
        for kind in ("tcp", "udp"):
            try:
                connections = psutil.net_connections(kind=kind)
            except (psutil.AccessDenied, psutil.Error):
                connections = []
            for conn in connections:
                if len(ports) >= PORT_LIMIT:
                    break
                laddr = cast(Any, conn.laddr)
                if laddr is None or not laddr.ip:
                    continue
                if kind == "tcp" and conn.status != "LISTEN":
                    continue
                ports.append(
                    {
                        "protocol": kind,
                        "local_address": laddr.ip[:64],
                        "local_port": int(laddr.port),
                        "pid": _as_int(conn.pid),
                    }
                )
        return ports

    # -- batch composition -------------------------------------------------

    def collect(
        self,
        *,
        include_details: bool = False,
        inventory: bool = True,
        events: list[dict[str, Any]] | None = None,
        file_changes: list[dict[str, Any]] | None = None,
        baseline_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build a complete schema-compatible telemetry batch.

        ``include_details`` adds processes and listening ports. ``inventory``
        controls whether the (expensive) inventory section is attached.
        """
        sections: dict[str, Any] = {
            "metrics": self.collect_metrics(),
        }
        if inventory:
            sections["inventory"] = self.collect_inventory()
        if include_details:
            sections["processes"] = self.collect_processes()
            sections["listening_ports"] = self.collect_listening_ports()
        if events:
            sections["events"] = events[:500]
        if file_changes:
            sections["file_changes"] = file_changes[:500]
        if baseline_results:
            sections["baseline_results"] = baseline_results[:200]
        return build_batch(collected_at=self._now_iso(), **sections)


def build_batch(
    *,
    batch_id: str | None = None,
    collected_at: str | None = None,
    **sections: Any,
) -> dict[str, Any]:
    """Compose a telemetry batch with required envelope fields."""
    return {
        "schema_version": 1,
        "batch_id": batch_id or str(uuid.uuid4()),
        "collected_at": collected_at or utcnow_iso(),
        **sections,
    }


def file_sha256(path: str, chunk_size: int = 1 << 20) -> str:
    """Lowercase hex SHA-256 of a file's contents."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


# -- helpers ---------------------------------------------------------------


def _clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, value))


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any, max_len: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _ip_addresses() -> list[str]:
    addresses: list[str] = []
    seen: set[str] = set()
    try:
        for addrs in psutil.net_if_addrs().values():
            for snic in addrs:
                ip = getattr(snic, "address", None)
                if not ip or ip in seen or len(addresses) >= INVENTORY_IP_LIMIT:
                    continue
                seen.add(ip)
                addresses.append(ip[:64])
    except (OSError, psutil.Error):
        pass
    return addresses
