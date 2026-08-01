"""Remote agent policy parsing and application.

The backend publishes the agent policy at ``/api/v1/agent/policy``. The
orchestrator merges the payload into an :class:`AgentPolicy` -- ``None``
intervals fall back to the local :class:`AgentConfig` -- and applies the
enabled collectors, FIM watch directories and event channels to the running
adapters. A failed policy pull keeps the previous policy and backs off before
retrying.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["AgentPolicy"]


def _opt_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _opt_bool(payload: dict[str, Any], key: str, default: bool) -> bool:
    value = payload.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return default


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    return []


@dataclass(frozen=True)
class AgentPolicy:
    """Remote policy values merged with local configuration defaults.

    Interval fields are ``None`` when the server did not specify them; the
    orchestrator falls back to the local configuration in that case. Toggle
    fields default to enabled and only switch off on an explicit signal.
    """

    revision: str | None = None
    collection_interval_seconds: int | None = None
    details_interval_seconds: int | None = None
    inventory_interval_seconds: int | None = None
    policy_refresh_interval_seconds: int | None = None
    enable_metrics: bool = True
    enable_details: bool = True
    enable_inventory: bool = True
    enable_events: bool = True
    enable_fim: bool = True
    enable_baseline: bool = True
    fim_watch_dirs: tuple[str, ...] = ()
    event_channels: tuple[str, ...] = ()

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> AgentPolicy:
        payload = payload or {}
        revision = payload.get("revision")
        return cls(
            revision=str(revision) if revision is not None else None,
            collection_interval_seconds=_opt_int(payload, "collection_interval_seconds"),
            details_interval_seconds=_opt_int(payload, "details_interval_seconds"),
            inventory_interval_seconds=_opt_int(payload, "inventory_interval_seconds"),
            policy_refresh_interval_seconds=_opt_int(payload, "policy_refresh_interval_seconds"),
            enable_metrics=_opt_bool(payload, "enable_metrics", True),
            enable_details=_opt_bool(payload, "enable_details", True),
            enable_inventory=_opt_bool(payload, "enable_inventory", True),
            enable_events=_opt_bool(payload, "enable_events", True),
            enable_fim=_opt_bool(payload, "enable_fim", True),
            enable_baseline=_opt_bool(payload, "enable_baseline", True),
            fim_watch_dirs=tuple(_str_list(payload.get("fim_watch_dirs"))),
            event_channels=tuple(_str_list(payload.get("event_channels"))),
        )
