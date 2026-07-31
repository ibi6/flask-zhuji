"""Agent configuration from defaults, a config file and environment.

Precedence: environment variables override file values override defaults.
All secrets (enrollment token, agent secret) are external: the token comes
from ``HOSTGUARD_ENROLL_TOKEN`` or the enroll CLI flag, and the agent secret
is only ever read back from the credential store.

URL validation requires HTTPS for anything that is not loopback; the
``development`` flag (``--dev`` / ``HOSTGUARD_DEV=1``) relaxes that rule for
local backends.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

__all__ = ["AgentConfig", "load_config"]

ENV_PREFIX = "HOSTGUARD_"

#: Default cap on stored payload bytes (256 MiB) -- mirrors the buffer.
DEFAULT_MAX_PAYLOAD_BYTES = 256 * 1024 * 1024


def _env(name: str) -> str | None:
    return os.environ.get(ENV_PREFIX + name)


@dataclass(frozen=True)
class AgentConfig:
    """Validated agent settings.

    ``server_url`` is normalized (trailing slash removed) and validated:
    HTTP is rejected for non-loopback hosts unless ``development`` is set.
    """

    server_url: str
    data_dir: Path
    enroll_token: str | None = None
    development: bool = False
    collection_interval_seconds: int = 10
    details_interval_seconds: int = 60
    inventory_interval_seconds: int = 600
    policy_refresh_interval_seconds: int = 300
    health_log_interval_seconds: int = 60
    base_backoff_seconds: int = 30
    max_backoff_seconds: int = 3600
    retention_days: int = 7
    max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES
    http_timeout_seconds: float = 15.0
    http_verify: bool = True
    fim_watch_dirs: tuple[str, ...] = field(default_factory=tuple)
    env_overrides: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        normalized = self._validate_url(self.server_url, self.development)
        object.__setattr__(self, "server_url", normalized)
        object.__setattr__(self, "data_dir", Path(self.data_dir).expanduser().resolve())
        for name in (
            "collection_interval_seconds",
            "details_interval_seconds",
            "inventory_interval_seconds",
            "policy_refresh_interval_seconds",
            "health_log_interval_seconds",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.retention_days <= 0:
            raise ValueError("retention_days must be positive")
        if self.max_payload_bytes <= 0:
            raise ValueError("max_payload_bytes must be positive")

    @staticmethod
    def _validate_url(server_url: str, development: bool) -> str:
        raw = (server_url or "").strip().rstrip("/")
        if not raw:
            raise ValueError("server_url is required")
        try:
            parts = urlsplit(raw)
        except ValueError as exc:
            raise ValueError(f"invalid server_url {server_url!r}: {exc}") from exc
        if parts.scheme not in ("http", "https"):
            raise ValueError(f"server_url must use http or https, got {parts.scheme!r}")
        if not parts.hostname:
            raise ValueError(f"server_url has no host: {server_url!r}")
        if parts.scheme == "http" and not (development or _is_loopback(parts.hostname)):
            raise ValueError(
                f"server_url must use HTTPS for remote hosts (got http://{parts.hostname}); "
                "pass --dev to allow plain HTTP for local development"
            )
        return raw

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_file(cls, path: Path) -> dict[str, Any]:
        """Parse a TOML or JSON config file into a settings mapping."""
        path = Path(path)
        try:
            if path.suffix == ".toml":
                with path.open("rb") as fh:
                    raw = tomllib.load(fh)
            else:
                with path.open("r", encoding="utf-8") as fh:
                    raw = json.load(fh)
        except (OSError, tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read config file {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"config file {path} must contain an object")
        return raw

    @classmethod
    def from_env(cls) -> dict[str, Any]:
        """Collect validated settings from ``HOSTGUARD_*`` variables."""
        values: dict[str, Any] = {}
        if (value := _env("SERVER_URL")) is not None:
            values["server_url"] = value
        if (value := _env("DATA_DIR")) is not None:
            values["data_dir"] = value
        if (value := _env("ENROLL_TOKEN")) is not None:
            values["enroll_token"] = value
        if (value := _env("DEV")) is not None:
            values["development"] = value.strip().lower() in ("1", "true", "yes")
        if (value := _env("HTTP_VERIFY")) is not None:
            values["http_verify"] = value.strip().lower() in ("1", "true", "yes")
        for name in (
            "COLLECTION_INTERVAL_SECONDS",
            "DETAILS_INTERVAL_SECONDS",
            "INVENTORY_INTERVAL_SECONDS",
            "POLICY_REFRESH_INTERVAL_SECONDS",
            "HEALTH_LOG_INTERVAL_SECONDS",
            "BASE_BACKOFF_SECONDS",
            "MAX_BACKOFF_SECONDS",
            "RETENTION_DAYS",
            "MAX_PAYLOAD_BYTES",
        ):
            if (value := _env(name)) is not None:
                values[_to_attr(name)] = _to_int(value, name)
        if (value := _env("HTTP_TIMEOUT_SECONDS")) is not None:
            values["http_timeout_seconds"] = float(value)
        if (value := _env("FIM_WATCH_DIRS")) is not None:
            values["fim_watch_dirs"] = tuple(p for p in value.split(os.pathsep) if p)
        return values


def _to_attr(env_name: str) -> str:
    return env_name.lower()


def _to_int(value: str, name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"HOSTGUARD_{name} must be an integer, got {value!r}") from exc


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def load_config(
    config_file: Path | None = None,
    *,
    server_url: str | None = None,
    data_dir: Path | None = None,
    development: bool | None = None,
) -> AgentConfig:
    """Build an :class:`AgentConfig` from file, env and explicit overrides."""
    values: dict[str, Any] = {}
    if config_file is not None:
        values.update(AgentConfig.from_file(config_file))
    values.update(AgentConfig.from_env())
    if server_url is not None:
        values["server_url"] = server_url
    if data_dir is not None:
        values["data_dir"] = data_dir
    if development is not None:
        values["development"] = development
    if "data_dir" not in values:
        values["data_dir"] = Path.home() / ".hostguard"
    if "server_url" not in values:
        raise ValueError(
            "server_url is required (set HOSTGUARD_SERVER_URL, a config file, or --server)"
        )
    return AgentConfig(**values)
