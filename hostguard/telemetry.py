from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

UuidStr = Annotated[str, Field()]


def _require_uuid(value: str) -> str:
    if str(UUID(value)) != value:
        raise ValueError("must be a canonical UUID string")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MetricSampleInput(StrictModel):
    cpu_percent: float = Field(ge=0, le=100)
    memory_percent: float = Field(ge=0, le=100)
    disk_percent: float = Field(ge=0, le=100)
    network_bytes_sent: int = Field(ge=0)
    network_bytes_recv: int = Field(ge=0)


class InventoryInput(StrictModel):
    hostname: str = Field(min_length=1, max_length=255)
    os: Literal["windows", "linux"]
    os_version: str = Field(default="", max_length=255)
    architecture: str = Field(default="", max_length=64)
    agent_version: str = Field(default="", max_length=32)
    boot_time: datetime | None = None
    ip_addresses: list[Annotated[str, Field(max_length=64)]] = Field(
        default_factory=list, max_length=32
    )


class ProcessInput(StrictModel):
    pid: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=255)
    executable: str | None = Field(default=None, max_length=1024)
    username: str | None = Field(default=None, max_length=255)
    started_at: datetime | None = None


class ListeningPortInput(StrictModel):
    protocol: Literal["tcp", "udp"]
    local_address: str = Field(min_length=1, max_length=64)
    local_port: int = Field(ge=0, le=65535)
    pid: int | None = Field(default=None, ge=0)


class SecurityEventInput(StrictModel):
    event_id: UuidStr
    event_type: str = Field(min_length=1, max_length=64)
    occurred_at: datetime
    severity: Literal["low", "medium", "high", "critical"]
    summary: str = Field(min_length=1, max_length=1024)
    source_ip: str | None = Field(default=None, max_length=64)
    username: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict, max_length=32)

    @field_validator("event_id")
    @classmethod
    def _event_id_is_uuid(cls, value: str) -> str:
        return _require_uuid(value)


class FileChangeInput(StrictModel):
    event_id: UuidStr
    path: str = Field(min_length=1, max_length=2048)
    change_type: Literal["created", "modified", "deleted", "permission_changed"]
    occurred_at: datetime
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    size: int | None = Field(default=None, ge=0)

    @field_validator("event_id")
    @classmethod
    def _event_id_is_uuid(cls, value: str) -> str:
        return _require_uuid(value)


class BaselineResultInput(StrictModel):
    check_id: str = Field(min_length=1, max_length=64)
    status: Literal["pass", "fail", "unavailable"]
    checked_at: datetime
    message: str = Field(max_length=1024)


class TelemetryBatchInput(StrictModel):
    """Mirrors ``contracts/telemetry.schema.json`` (telemetry-v1)."""

    schema_version: Literal[1] = 1
    batch_id: UuidStr
    collected_at: datetime
    metrics: MetricSampleInput
    inventory: InventoryInput | None = None
    processes: list[ProcessInput] = Field(default_factory=list, max_length=2000)
    listening_ports: list[ListeningPortInput] = Field(default_factory=list, max_length=2000)
    events: list[SecurityEventInput] = Field(default_factory=list, max_length=500)
    file_changes: list[FileChangeInput] = Field(default_factory=list, max_length=500)
    baseline_results: list[BaselineResultInput] = Field(default_factory=list, max_length=200)

    @field_validator("batch_id")
    @classmethod
    def _batch_id_is_uuid(cls, value: str) -> str:
        return _require_uuid(value)
