from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient

from hostguard.models import (
    BaselineResult,
    FileChange,
    InventorySnapshot,
    ListeningPortSnapshot,
    MetricSample,
    ProcessSnapshot,
    SecurityEvent,
)

from .conftest import create_enrollment_token, enroll_agent, post_signed_batch, valid_batch


def _enrolled(client: FlaskClient, app: Flask) -> tuple[str, str]:
    token = create_enrollment_token(app)
    agent = enroll_agent(client, token)
    return agent["agent_id"], agent["agent_secret"]


def test_batch_persists_all_telemetry_tables(client: FlaskClient, app: Flask) -> None:
    agent_id, secret = _enrolled(client, app)
    payload = valid_batch()

    response = post_signed_batch(client, agent_id, secret, payload)
    assert response.status_code == 202
    assert response.get_json()["accepted"] is True

    with app.app_context():
        batch = payload["batch_id"]
        assert MetricSample.query.filter_by(batch_id=batch).count() == 1
        assert InventorySnapshot.query.filter_by(batch_id=batch).count() == 1
        assert ProcessSnapshot.query.filter_by(batch_id=batch).count() == 1
        assert ListeningPortSnapshot.query.filter_by(batch_id=batch).count() == 1
        assert SecurityEvent.query.filter_by(batch_id=batch).count() == 1
        assert FileChange.query.filter_by(batch_id=batch).count() == 1
        assert BaselineResult.query.filter_by(batch_id=batch).count() == 1


def test_invalid_telemetry_is_rejected_and_not_persisted(
    client: FlaskClient, app: Flask
) -> None:
    agent_id, secret = _enrolled(client, app)
    payload = valid_batch(
        metrics={
            "cpu_percent": 150.0,
            "memory_percent": 30.0,
            "disk_percent": 40.0,
            "network_bytes_sent": 1,
            "network_bytes_recv": 2,
        }
    )

    response = post_signed_batch(client, agent_id, secret, payload)
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"

    with app.app_context():
        assert MetricSample.query.count() == 0
        assert SecurityEvent.query.count() == 0
        assert BaselineResult.query.count() == 0


def test_duplicate_batch_is_idempotent_and_rejected(
    client: FlaskClient, app: Flask
) -> None:
    agent_id, secret = _enrolled(client, app)
    batch_id = "6f5bf46b-7d42-4e6c-9a2d-4f2c0d1a5b31"

    first = post_signed_batch(client, agent_id, secret, valid_batch(batch_id=batch_id))
    assert first.status_code == 202

    second = post_signed_batch(client, agent_id, secret, valid_batch(batch_id=batch_id))
    assert second.status_code == 409
    assert second.get_json()["error"]["code"] == "duplicate_batch"

    with app.app_context():
        assert MetricSample.query.filter_by(batch_id=batch_id).count() == 1
