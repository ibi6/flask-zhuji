from __future__ import annotations

import hashlib
import secrets
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from ..authz import write_audit
from ..errors import ApiError
from ..extensions import db
from ..models import (
    AgentCredential,
    BaselineResult,
    EnrollmentToken,
    FileChange,
    Host,
    InventorySnapshot,
    ListeningPortSnapshot,
    MetricSample,
    ProcessSnapshot,
    SecurityEvent,
    utcnow,
)
from ..rule_engine import run_rule_evaluation
from ..schemas import AgentEnrollInput
from ..security import (
    agent_canonical_message,
    consume_agent_nonce,
    decrypt_agent_secret,
    encrypt_agent_secret,
    hash_token,
    sign_message,
    verify_agent_signature,
)
from ..telemetry import TelemetryBatchInput

bp = Blueprint("agent", __name__, url_prefix="/api/v1/agent")

POLICY = {
    "policy_version": 1,
    "collect_interval_seconds": 60,
    "batch_max_items": 2000,
    "report_interval_minutes": 30,
}


@bp.before_request
def _verify_signed_request() -> None:
    """Authenticate every agent request except enrollment (uses a one-time token)."""
    if request.endpoint == "agent.enroll_agent":
        return

    agent_id = request.headers.get("X-HG-Agent-Id")
    timestamp = request.headers.get("X-HG-Timestamp")
    nonce = request.headers.get("X-HG-Nonce")
    signature = request.headers.get("X-HG-Signature")
    if not agent_id or not timestamp or not nonce or not signature:
        raise ApiError(
            "agent_signature_required",
            "The request is missing agent signing headers.",
            401,
        )

    host = db.session.get(Host, agent_id)
    if host is None:
        raise ApiError("agent_unknown", "The agent is not registered.", 401)
    credential = host.credential
    if credential is None or credential.revoked_at is not None:
        raise ApiError("agent_credential_revoked", "The agent credential is not valid.", 403)
    if credential.encrypted_secret is None:
        raise ApiError("agent_credential_invalid", "The agent credential is invalid.", 403)

    secret = decrypt_agent_secret(credential.encrypted_secret)
    raw_body = request.get_data()
    timestamp, nonce = verify_agent_signature(secret, raw_body)
    consume_agent_nonce(host.id, nonce)
    g.agent_host = host
    g.agent_secret = secret
    g.agent_timestamp = timestamp
    g.agent_nonce = nonce


@bp.post("/enroll")
def enroll_agent() -> tuple[Any, int]:
    """One-time enrollment: returns the agent secret exactly once."""
    payload = AgentEnrollInput.model_validate(request.get_json(silent=True) or {})
    token = EnrollmentToken.query.filter_by(token_hash=hash_token(payload.token)).first()
    if token is None or token.expires_at < utcnow():
        raise ApiError(
            "enrollment_token_invalid", "The enrollment token is invalid or expired.", 403
        )
    if token.used_at is not None:
        raise ApiError("enrollment_token_used", "The enrollment token has already been used.", 409)

    secret_bytes = secrets.token_bytes(32)
    host = Host(
        hostname=payload.hostname,
        os=payload.os,
        os_version=payload.os_version or None,
        architecture=payload.architecture or None,
        agent_version=payload.agent_version or None,
        source="real",
        status="online",
        last_seen_at=utcnow(),
    )
    db.session.add(host)
    db.session.flush()
    db.session.add(
        AgentCredential(
            host_id=host.id,
            secret_hash=hashlib.sha256(secret_bytes).hexdigest(),
            encrypted_secret=encrypt_agent_secret(secret_bytes),
        )
    )
    token.used_at = utcnow()
    token.used_by_host_id = host.id
    write_audit("agent.enroll", "host", host.id)
    db.session.commit()
    return (
        jsonify(
            {
                "agent_id": host.id,
                "agent_secret": secret_bytes.hex(),
                "policy_version": POLICY["policy_version"],
            }
        ),
        201,
    )


@bp.get("/policy")
def get_agent_policy() -> tuple[Any, int]:
    body = jsonify(POLICY).get_data()
    message = agent_canonical_message(
        g.agent_timestamp, g.agent_nonce, request.method, request.path, body
    )
    signature = sign_message(g.agent_secret, message)
    response = jsonify(POLICY)
    response.headers["X-HG-Signature"] = signature
    return response, 200


@bp.post("/batches")
def ingest_telemetry_batch() -> tuple[Any, int]:
    host = g.agent_host
    try:
        payload = TelemetryBatchInput.model_validate_json(request.get_data())
    except ValidationError:
        raise
    except ValueError as exc:
        raise ApiError("invalid_json", "The request body is not valid JSON.", 400) from exc

    if MetricSample.query.filter_by(batch_id=payload.batch_id).first() is not None:
        raise ApiError("duplicate_batch", "This batch has already been accepted.", 409)

    event_ids = [event.event_id for event in payload.events]
    event_ids += [change.event_id for change in payload.file_changes]
    if event_ids:
        if SecurityEvent.query.filter(SecurityEvent.id.in_(event_ids)).first() is not None:
            raise ApiError(
                "duplicate_event", "An event in this batch has already been accepted.", 409
            )
        if FileChange.query.filter(FileChange.id.in_(event_ids)).first() is not None:
            raise ApiError(
                "duplicate_event", "An event in this batch has already been accepted.", 409
            )

    _persist_batch(host, payload)

    host.last_seen_at = utcnow()
    host.status = "online"
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError(
            "duplicate_batch", "This batch has already been accepted.", 409
        ) from None

    try:
        run_rule_evaluation(host_id=host.id, batch_id=payload.batch_id)
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "rule_evaluation_failed",
            extra={"request_id": getattr(g, "request_id", ""), "host_id": host.id},
        )
    return jsonify({"accepted": True, "batch_id": payload.batch_id}), 202


def _persist_batch(host: Host, payload: TelemetryBatchInput) -> None:
    metrics = payload.metrics
    db.session.add(
        MetricSample(
            host_id=host.id,
            batch_id=payload.batch_id,
            collected_at=payload.collected_at,
            cpu_percent=metrics.cpu_percent,
            memory_percent=metrics.memory_percent,
            disk_percent=metrics.disk_percent,
            network_bytes_sent=metrics.network_bytes_sent,
            network_bytes_recv=metrics.network_bytes_recv,
        )
    )

    inventory = None
    if payload.inventory is not None:
        inventory = InventorySnapshot(
            host_id=host.id,
            batch_id=payload.batch_id,
            hostname=payload.inventory.hostname,
            os=payload.inventory.os,
            os_version=payload.inventory.os_version,
            architecture=payload.inventory.architecture,
            agent_version=payload.inventory.agent_version,
            boot_time=payload.inventory.boot_time,
            ip_addresses=payload.inventory.ip_addresses,
        )
        db.session.add(inventory)
        db.session.flush()

    for process in payload.processes:
        db.session.add(
            ProcessSnapshot(
                host_id=host.id,
                batch_id=payload.batch_id,
                inventory_id=inventory.id if inventory is not None else None,
                pid=process.pid,
                name=process.name,
                executable=process.executable,
                username=process.username,
                started_at=process.started_at,
            )
        )

    for port in payload.listening_ports:
        db.session.add(
            ListeningPortSnapshot(
                host_id=host.id,
                batch_id=payload.batch_id,
                protocol=port.protocol,
                local_address=port.local_address,
                local_port=port.local_port,
                pid=port.pid,
            )
        )

    for event in payload.events:
        db.session.add(
            SecurityEvent(
                id=event.event_id,
                host_id=host.id,
                batch_id=payload.batch_id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                severity=event.severity,
                summary=event.summary,
                source_ip=event.source_ip,
                username=event.username,
                metadata_=event.metadata,
            )
        )

    for change in payload.file_changes:
        db.session.add(
            FileChange(
                id=change.event_id,
                host_id=host.id,
                batch_id=payload.batch_id,
                path=change.path,
                change_type=change.change_type,
                occurred_at=change.occurred_at,
                sha256=change.sha256,
                size=change.size,
            )
        )

    for result in payload.baseline_results:
        db.session.add(
            BaselineResult(
                host_id=host.id,
                batch_id=payload.batch_id,
                check_id=result.check_id,
                status=result.status,
                checked_at=result.checked_at,
                message=result.message,
            )
        )
