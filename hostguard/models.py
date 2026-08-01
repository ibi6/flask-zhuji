# mypy: disable-error-code="misc,name-defined"
# flask-sqlalchemy's db.Model base class is not statically typed; see
# https://github.com/pallets-eco/flask-sqlalchemy for the known limitation.

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    TypeDecorator,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .extensions import db


class UTCDateTime(TypeDecorator[datetime]):
    """Stores naive UTC instants and returns timezone-aware UTC datetimes.

    Keeps naive/aware comparisons consistent across SQLite and PostgreSQL.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(UTC)
        return value.replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


def isoformat_utc(value: datetime | None) -> str | None:
    """Serialize a datetime as UTC ISO-8601 with a trailing ``Z`` (contract convention)."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def new_id() -> str:
    return str(uuid4())


password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow
    )


class User(TimestampMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    sessions: Mapped[list[WebSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @validates("username")
    def normalize_username(self, _key: str, value: str) -> str:
        return value.strip().lower()

    @validates("email")
    def normalize_email(self, _key: str, value: str) -> str:
        return value.strip().lower()

    def set_password(self, password: str) -> None:
        self.password_hash = password_hasher.hash(password)

    def verify_password(self, password: str) -> bool:
        try:
            valid = password_hasher.verify(self.password_hash, password)
        except (InvalidHashError, VerifyMismatchError):
            return False
        if valid and password_hasher.check_needs_rehash(self.password_hash):
            self.password_hash = password_hasher.hash(password)
        return valid

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
        }


class WebSession(db.Model):
    """Server-side browser session. Only the SHA-256 hash of the token is stored."""

    __tablename__ = "web_sessions"
    __table_args__ = (Index("ix_web_sessions_validity", "expires_at", "revoked_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))

    user: Mapped[User] = relationship(back_populates="sessions")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128))
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)

    actor: Mapped[User | None] = relationship()


class Host(TimestampMixin, db.Model):
    __tablename__ = "hosts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    os: Mapped[str] = mapped_column(String(16), nullable=False)
    os_version: Mapped[str | None] = mapped_column(String(255))
    architecture: Mapped[str | None] = mapped_column(String(64))
    agent_version: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="real")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="offline", index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)

    credential: Mapped[AgentCredential | None] = relationship(
        back_populates="host", uselist=False, cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "hostname": self.hostname,
            "os": self.os,
            "os_version": self.os_version,
            "architecture": self.architecture,
            "agent_version": self.agent_version,
            "source": self.source,
            "status": self.status,
            "last_seen_at": isoformat_utc(self.last_seen_at),
            "risk_score": self.risk_score,
        }


class AgentCredential(db.Model):
    """Agent secret, stored hashed and encrypted (Fernet) so signatures can be verified."""

    __tablename__ = "agent_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    host_id: Mapped[str] = mapped_column(
        ForeignKey("hosts.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_secret: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    rotated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)

    host: Mapped[Host] = relationship(back_populates="credential")


class EnrollmentToken(db.Model):
    __tablename__ = "enrollment_tokens"
    __table_args__ = (Index("ix_enrollment_token_validity", "expires_at", "used_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    used_by_host_id: Mapped[str | None] = mapped_column(ForeignKey("hosts.id", ondelete="SET NULL"))


class AgentNonce(db.Model):
    """One-time request nonce for signed agent requests (retained for ten minutes)."""

    __tablename__ = "agent_nonces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(
        ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nonce: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)


class MetricSample(db.Model):
    __tablename__ = "metric_samples"
    __table_args__ = (Index("ix_metric_samples_batch_host", "batch_id", "host_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    host_id: Mapped[str] = mapped_column(
        ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False)
    memory_percent: Mapped[float] = mapped_column(Float, nullable=False)
    disk_percent: Mapped[float] = mapped_column(Float, nullable=False)
    network_bytes_sent: Mapped[int] = mapped_column(BigInteger, nullable=False)
    network_bytes_recv: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class InventorySnapshot(db.Model):
    __tablename__ = "inventory_snapshots"
    __table_args__ = (Index("ix_inventory_batch_host", "batch_id", "host_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    host_id: Mapped[str] = mapped_column(
        ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    os: Mapped[str] = mapped_column(String(16), nullable=False)
    os_version: Mapped[str | None] = mapped_column(String(255))
    architecture: Mapped[str | None] = mapped_column(String(64))
    agent_version: Mapped[str | None] = mapped_column(String(32))
    boot_time: Mapped[datetime | None] = mapped_column(UTCDateTime())
    ip_addresses: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ProcessSnapshot(db.Model):
    __tablename__ = "process_snapshots"
    __table_args__ = (Index("ix_process_snapshots_batch", "batch_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    host_id: Mapped[str] = mapped_column(
        ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    inventory_id: Mapped[str | None] = mapped_column(
        ForeignKey("inventory_snapshots.id", ondelete="SET NULL"), index=True
    )
    pid: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    executable: Mapped[str | None] = mapped_column(String(1024))
    username: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ListeningPortSnapshot(db.Model):
    __tablename__ = "listening_port_snapshots"
    __table_args__ = (Index("ix_port_snapshots_batch", "batch_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    host_id: Mapped[str] = mapped_column(
        ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    protocol: Mapped[str] = mapped_column(String(8), nullable=False)
    local_address: Mapped[str] = mapped_column(String(64), nullable=False)
    local_port: Mapped[int] = mapped_column(Integer, nullable=False)
    pid: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class SecurityEvent(db.Model):
    """Security event. ``id`` is the agent-generated ``event_id`` (idempotency key)."""

    __tablename__ = "security_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    host_id: Mapped[str] = mapped_column(
        ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_ip: Mapped[str | None] = mapped_column(String(64))
    username: Mapped[str | None] = mapped_column(String(255))
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class FileChange(db.Model):
    """File change event. ``id`` is the agent-generated ``event_id`` (idempotency key)."""

    __tablename__ = "file_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    host_id: Mapped[str] = mapped_column(
        ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    sha256: Mapped[str | None] = mapped_column(String(64))
    size: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class BaselineResult(db.Model):
    __tablename__ = "baseline_results"
    __table_args__ = (Index("ix_baseline_results_batch", "batch_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    host_id: Mapped[str] = mapped_column(
        ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    check_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)


class DetectionRule(TimestampMixin, db.Model):
    __tablename__ = "detection_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024))
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    criteria: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "rule_type": self.rule_type,
            "enabled": self.enabled,
            "severity": self.severity,
            "criteria": self.criteria,
            "created_at": isoformat_utc(self.created_at),
            "updated_at": isoformat_utc(self.updated_at),
        }


class Alert(TimestampMixin, db.Model):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("detection_rules.id", ondelete="SET NULL"), index=True
    )
    host_id: Mapped[str | None] = mapped_column(
        ForeignKey("hosts.id", ondelete="CASCADE"), index=True
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    transitions: Mapped[list[AlertTransition]] = relationship(
        back_populates="alert", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "host_id": self.host_id,
            "severity": self.severity,
            "status": self.status,
            "title": self.title,
            "description": self.description,
            "first_seen_at": isoformat_utc(self.first_seen_at),
            "last_seen_at": isoformat_utc(self.last_seen_at),
            "resolved_at": isoformat_utc(self.resolved_at),
            "event_count": self.event_count,
            "created_at": isoformat_utc(self.created_at),
            "updated_at": isoformat_utc(self.updated_at),
        }


class AlertTransition(db.Model):
    __tablename__ = "alert_transitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    alert_id: Mapped[str] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str] = mapped_column(String(16), nullable=False)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    reason: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)

    alert: Mapped[Alert] = relationship(back_populates="transitions")

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "alert_id": self.alert_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "actor_user_id": self.actor_user_id,
            "reason": self.reason,
            "created_at": isoformat_utc(self.created_at),
        }


class BackgroundJob(TimestampMixin, db.Model):
    __tablename__ = "background_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "job_type": self.job_type,
            "status": self.status,
            "payload": self.payload,
            "started_at": isoformat_utc(self.started_at),
            "finished_at": isoformat_utc(self.finished_at),
            "error": self.error,
            "created_at": isoformat_utc(self.created_at),
        }


class NotificationChannel(TimestampMixin, db.Model):
    __tablename__ = "notification_channels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    channel_type: Mapped[str] = mapped_column(String(32), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "channel_type": self.channel_type,
            "enabled": self.enabled,
            "created_at": isoformat_utc(self.created_at),
            "updated_at": isoformat_utc(self.updated_at),
        }


class NotificationDelivery(TimestampMixin, db.Model):
    __tablename__ = "notification_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    alert_id: Mapped[str | None] = mapped_column(
        ForeignKey("alerts.id", ondelete="SET NULL"), index=True
    )
    channel_id: Mapped[str | None] = mapped_column(
        ForeignKey("notification_channels.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "alert_id": self.alert_id,
            "channel_id": self.channel_id,
            "status": self.status,
            "sent_at": isoformat_utc(self.sent_at),
            "error": self.error,
            "attempts": self.attempts,
            "created_at": isoformat_utc(self.created_at),
        }


class ReportJob(TimestampMixin, db.Model):
    __tablename__ = "report_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("background_jobs.id", ondelete="SET NULL"), index=True
    )
    report_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    file_path: Mapped[str | None] = mapped_column(String(1024))
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "report_type": self.report_type,
            "parameters": self.parameters,
            "status": self.status,
            "file_path": self.file_path,
            "expires_at": isoformat_utc(self.expires_at),
            "created_at": isoformat_utc(self.created_at),
            "updated_at": isoformat_utc(self.updated_at),
        }
