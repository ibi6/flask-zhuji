from __future__ import annotations

from uuid import uuid4

from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import joinedload

from hostguard.extensions import db
from hostguard.models import Alert, DetectionRule

from .conftest import create_enrollment_token, enroll_agent, post_signed_batch, valid_batch


def _enrolled(client: FlaskClient, app: Flask) -> tuple[str, str]:
    token = create_enrollment_token(app)
    agent = enroll_agent(client, token)
    return agent["agent_id"], agent["agent_secret"]


def _add_rule(app: Flask, **kwargs: object) -> str:
    with app.app_context():
        rule = DetectionRule(**kwargs)
        db.session.add(rule)
        db.session.commit()
        return rule.id


def _get_alerts(app: Flask, rule_id: str, host_id: str) -> list[Alert]:
    with app.app_context():
        return (
            Alert.query.options(joinedload(Alert.transitions))
            .filter_by(rule_id=rule_id, host_id=host_id)
            .all()
        )


def test_cpu_threshold_rule_generates_alert_on_ingest(
    client: FlaskClient, app: Flask
) -> None:
    rule_id = _add_rule(
        app,
        name="high-cpu",
        rule_type="cpu_usage",
        enabled=True,
        severity="high",
        criteria={"threshold": 10},
    )
    agent_id, secret = _enrolled(client, app)
    payload = valid_batch()  # cpu_percent = 12.5 >= 10

    response = post_signed_batch(client, agent_id, secret, payload)
    assert response.status_code == 202

    alerts = _get_alerts(app, rule_id, agent_id)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.status == "open"
    assert alert.severity == "high"
    assert alert.event_count == 1
    assert alert.host_id == agent_id
    assert alert.title == "high-cpu"
    with app.app_context():
        assert len(alert.transitions) == 1
        assert alert.transitions[0].from_status == "new"
        assert alert.transitions[0].to_status == "open"


def test_open_alert_is_suppressed_and_incremented(
    client: FlaskClient, app: Flask
) -> None:
    rule_id = _add_rule(
        app,
        name="high-cpu",
        rule_type="cpu_usage",
        enabled=True,
        severity="medium",
        criteria={"threshold": 10},
    )
    agent_id, secret = _enrolled(client, app)

    assert (
        post_signed_batch(client, agent_id, secret, valid_batch()).status_code == 202
    )
    # A later batch on the same host+rule must not create a duplicate open alert.
    assert (
        post_signed_batch(client, agent_id, secret, valid_batch()).status_code == 202
    )

    alerts = _get_alerts(app, rule_id, agent_id)
    assert len(alerts) == 1
    assert alerts[0].event_count == 2
    assert alerts[0].status == "open"


def test_high_severity_event_rule_generates_alert(
    client: FlaskClient, app: Flask
) -> None:
    rule_id = _add_rule(
        app,
        name="crit-events",
        rule_type="high_severity_event",
        enabled=True,
        severity="critical",
        criteria={"min_severity": "high"},
    )
    agent_id, secret = _enrolled(client, app)
    payload = valid_batch(
        events=[
            {
                "event_id": str(uuid4()),
                "event_type": "brute_force",
                "occurred_at": "2026-07-31T09:59:00Z",
                "severity": "critical",
                "summary": "repeated failed logins",
            }
        ]
    )

    response = post_signed_batch(client, agent_id, secret, payload)
    assert response.status_code == 202

    alerts = _get_alerts(app, rule_id, agent_id)
    assert len(alerts) == 1
    assert alerts[0].severity == "critical"


def test_low_severity_event_does_not_trigger_high_severity_rule(
    client: FlaskClient, app: Flask
) -> None:
    rule_id = _add_rule(
        app,
        name="crit-events",
        rule_type="high_severity_event",
        enabled=True,
        severity="critical",
        criteria={"min_severity": "high"},
    )
    agent_id, secret = _enrolled(client, app)
    payload = valid_batch()  # default event severity is "medium" -> below threshold

    assert post_signed_batch(client, agent_id, secret, payload).status_code == 202
    assert _get_alerts(app, rule_id, agent_id) == []


def test_new_process_rule_triggers_once_for_first_occurrence(
    client: FlaskClient, app: Flask
) -> None:
    rule_id = _add_rule(
        app,
        name="new-proc",
        rule_type="new_process",
        enabled=True,
        severity="medium",
        criteria={},
    )
    agent_id, secret = _enrolled(client, app)

    # First batch introduces svchost.exe -> alert.
    assert (
        post_signed_batch(client, agent_id, secret, valid_batch()).status_code == 202
    )
    assert len(_get_alerts(app, rule_id, agent_id)) == 1

    # Second batch repeats the same process -> not a new process anymore.
    assert (
        post_signed_batch(client, agent_id, secret, valid_batch()).status_code == 202
    )
    assert len(_get_alerts(app, rule_id, agent_id)) == 1
