from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from flask import Flask
from flask.testing import FlaskClient

from hostguard.extensions import db
from hostguard.models import (
    AgentNonce,
    FileChange,
    Host,
    MetricSample,
    SecurityEvent,
    WebSession,
)
from hostguard.security import AGENT_CLOCK_SKEW_SECONDS

from .conftest import (
    agent_headers,
    create_enrollment_token,
    enroll_agent,
    post_signed_batch,
    valid_batch,
)


def test_enroll_returns_secret_exactly_once(client: FlaskClient, app: Flask) -> None:
    token = create_enrollment_token(app)
    first = enroll_agent(client, token)
    assert first["agent_id"]
    assert len(first["agent_secret"]) == 64

    second = client.post(
        "/api/v1/agent/enroll",
        json={"token": token, "hostname": "agent-02", "os": "linux"},
    )
    assert second.status_code == 409
    assert second.get_json()["error"]["code"] == "enrollment_token_used"

    with app.app_context():
        assert Host.query.count() == 1
        assert AgentNonce.query.count() == 0


def test_enroll_rejects_invalid_token(client: FlaskClient, app: Flask) -> None:
    response = client.post(
        "/api/v1/agent/enroll",
        json={"token": "not-a-real-token", "hostname": "x", "os": "linux"},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "enrollment_token_invalid"


def test_enroll_rejects_expired_token(client: FlaskClient, app: Flask) -> None:
    token = create_enrollment_token(app, expires_hours=-1)
    response = client.post(
        "/api/v1/agent/enroll",
        json={"token": token, "hostname": "x", "os": "linux"},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "enrollment_token_invalid"


def test_enroll_validates_payload(client: FlaskClient, app: Flask) -> None:
    token = create_enrollment_token(app)
    response = client.post(
        "/api/v1/agent/enroll",
        json={"token": token, "hostname": "x", "os": "freebsd"},
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_ingest_requires_signing_headers(client: FlaskClient, app: Flask) -> None:
    response = client.post(
        "/api/v1/agent/batches",
        data=json.dumps(valid_batch()),
        content_type="application/json",
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "agent_signature_required"


def test_ingest_rejects_unknown_agent(client: FlaskClient, app: Flask) -> None:
    token = create_enrollment_token(app)
    agent = enroll_agent(client, token)
    headers = agent_headers(
        str(uuid4()), agent["agent_secret"], "POST", "/api/v1/agent/batches", b"{}"
    )
    response = client.post(
        "/api/v1/agent/batches", data=b"{}", content_type="application/json", headers=headers
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "agent_unknown"


def test_ingest_rejects_bad_signature(client: FlaskClient, app: Flask) -> None:
    token = create_enrollment_token(app)
    agent = enroll_agent(client, token)
    body = json.dumps(valid_batch()).encode()
    headers = agent_headers(agent["agent_id"], agent["agent_secret"], "POST", "/api/v1/agent/batches", body)
    headers["X-HG-Signature"] = "f" * 64

    response = client.post(
        "/api/v1/agent/batches", data=body, content_type="application/json", headers=headers
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "invalid_signature"


def test_ingest_rejects_stale_timestamp(client: FlaskClient, app: Flask) -> None:
    token = create_enrollment_token(app)
    agent = enroll_agent(client, token)
    body = json.dumps(valid_batch()).encode()
    stale = (
        datetime.now(timezone.utc) - timedelta(seconds=AGENT_CLOCK_SKEW_SECONDS + 60)
    ).isoformat().replace("+00:00", "Z")
    headers = agent_headers(
        agent["agent_id"], agent["agent_secret"], "POST", "/api/v1/agent/batches", body, timestamp=stale
    )

    response = client.post(
        "/api/v1/agent/batches", data=body, content_type="application/json", headers=headers
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "agent_timestamp_invalid"


def test_ingest_rejects_nonce_replay(client: FlaskClient, app: Flask) -> None:
    token = create_enrollment_token(app)
    agent = enroll_agent(client, token)
    body = json.dumps(valid_batch()).encode()
    nonce = str(uuid4())
    headers = agent_headers(
        agent["agent_id"], agent["agent_secret"], "POST", "/api/v1/agent/batches", body, nonce=nonce
    )

    first = client.post(
        "/api/v1/agent/batches", data=body, content_type="application/json", headers=headers
    )
    assert first.status_code == 202

    replay = client.post(
        "/api/v1/agent/batches", data=body, content_type="application/json", headers=headers
    )
    assert replay.status_code == 403
    assert replay.get_json()["error"]["code"] == "agent_nonce_replay"


def test_valid_batch_is_persisted(client: FlaskClient, app: Flask) -> None:
    token = create_enrollment_token(app)
    agent = enroll_agent(client, token)
    payload = valid_batch()

    response = post_signed_batch(client, agent["agent_id"], agent["agent_secret"], payload)
    assert response.status_code == 202
    assert response.get_json()["accepted"] is True

    with app.app_context():
        host = db.session.get(Host, agent["agent_id"])
        assert host is not None
        assert host.status == "online"
        assert host.last_seen_at is not None
        assert MetricSample.query.filter_by(batch_id=payload["batch_id"]).count() == 1
        assert SecurityEvent.query.count() == 1
        assert FileChange.query.count() == 1


def test_duplicate_batch_id_is_rejected(client: FlaskClient, app: Flask) -> None:
    token = create_enrollment_token(app)
    agent = enroll_agent(client, token)
    batch_id = str(uuid4())
    first_payload = valid_batch(batch_id=batch_id)

    first = post_signed_batch(
        client, agent["agent_id"], agent["agent_secret"], first_payload
    )
    assert first.status_code == 202

    second = post_signed_batch(
        client, agent["agent_id"], agent["agent_secret"], valid_batch(batch_id=batch_id)
    )
    assert second.status_code == 409
    assert second.get_json()["error"]["code"] == "duplicate_batch"


def test_duplicate_event_id_is_rejected(client: FlaskClient, app: Flask) -> None:
    token = create_enrollment_token(app)
    agent = enroll_agent(client, token)
    event_id = str(uuid4())
    first_payload = valid_batch(events=[_event(event_id)])

    assert post_signed_batch(client, agent["agent_id"], agent["agent_secret"], first_payload).status_code == 202

    second_payload = valid_batch(events=[_event(event_id)])
    response = post_signed_batch(client, agent["agent_id"], agent["agent_secret"], second_payload)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "duplicate_event"


def test_invalid_telemetry_is_rejected(client: FlaskClient, app: Flask) -> None:
    token = create_enrollment_token(app)
    agent = enroll_agent(client, token)

    bad = valid_batch(schema_version=2)
    response = post_signed_batch(client, agent["agent_id"], agent["agent_secret"], bad)
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"

    missing_metrics = valid_batch()
    del missing_metrics["metrics"]
    response = post_signed_batch(client, agent["agent_id"], agent["agent_secret"], missing_metrics)
    assert response.status_code == 422

    bad_severity = valid_batch(
        events=[_event(str(uuid4()), severity="catastrophic")]
    )
    response = post_signed_batch(client, agent["agent_id"], agent["agent_secret"], bad_severity)
    assert response.status_code == 422


def test_policy_requires_signed_agent(client: FlaskClient, app: Flask) -> None:
    response = client.get("/api/v1/agent/policy")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "agent_signature_required"


def test_policy_is_returned_and_signed(client: FlaskClient, app: Flask) -> None:
    token = create_enrollment_token(app)
    agent = enroll_agent(client, token)
    raw = b""
    headers = agent_headers(
        agent["agent_id"], agent["agent_secret"], "GET", "/api/v1/agent/policy", raw
    )
    response = client.get("/api/v1/agent/policy", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["policy_version"] == 1
    assert response.headers.get("X-HG-Signature")


def test_agent_responses_never_contain_secret_after_enroll(
    client: FlaskClient, app: Flask
) -> None:
    token = create_enrollment_token(app)
    agent = enroll_agent(client, token)
    with app.app_context():
        web_sessions = WebSession.query.count()
        assert web_sessions == 0

    # Enroll response contains the secret once; later responses must not.
    response = client.get("/api/v1/agent/policy")
    assert agent["agent_secret"] not in response.get_data(as_text=True)


def _event(event_id: str, severity: str = "high") -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": "process_creation",
        "occurred_at": "2026-07-31T09:59:00Z",
        "severity": severity,
        "summary": "Suspicious process",
    }
