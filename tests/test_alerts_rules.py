from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient

from hostguard.extensions import db
from hostguard.models import Alert, DetectionRule, User

from .conftest import csrf_token, login, login_as_admin


def _seed(client: FlaskClient, app: Flask) -> tuple[Alert, DetectionRule]:
    with app.app_context():
        alert = Alert(
            title="Suspicious process",
            severity="high",
            status="open",
            description="process_creation outside system dirs",
        )
        rule = DetectionRule(
            name="suspicious-process",
            rule_type="signature",
            enabled=True,
            severity="high",
            criteria={"path": "temp"},
        )
        db.session.add_all([alert, rule])
        db.session.commit()
        db.session.refresh(alert)
        db.session.refresh(rule)
        db.session.expunge(alert)
        db.session.expunge(rule)
        return alert, rule


def test_list_alerts_is_paginated_and_filterable(
    client: FlaskClient, app: Flask, admin: User
) -> None:
    login_as_admin(client, admin)
    with app.app_context():
        for title in ("a", "b", "c"):
            db.session.add(Alert(title=title, severity="low", status="open", description=None))
        db.session.commit()

    response = client.get("/api/v1/alerts?page=2&page_size=2")
    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 3  # 3 alerts created
    assert len(body["items"]) == 1
    assert body["page"] == 2

    filtered = client.get("/api/v1/alerts?severity=low")
    assert filtered.get_json()["total"] == 3


def test_alert_detail_includes_transitions(
    client: FlaskClient, app: Flask, admin: User
) -> None:
    alert, _ = _seed(client, app)
    login_as_admin(client, admin)

    response = client.get(f"/api/v1/alerts/{alert.id}")
    assert response.status_code == 200
    body = response.get_json()["alert"]
    assert body["status"] == "open"
    assert body["transitions"] == []


def test_alert_transition_resolves_and_records_audit(
    client: FlaskClient, app: Flask, admin: User
) -> None:
    alert, _ = _seed(client, app)
    login_as_admin(client, admin)

    response = client.post(
        f"/api/v1/alerts/{alert.id}/transitions",
        json={"status": "resolved", "reason": "false positive"},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 200
    alert_body = response.get_json()["alert"]
    assert alert_body["status"] == "resolved"
    assert alert_body["resolved_at"] is not None

    with app.app_context():
        fresh = db.session.get(Alert, alert.id)
        assert fresh is not None
        assert fresh.status == "resolved"
        assert len(fresh.transitions) == 1
        assert fresh.transitions[0].from_status == "open"
        assert fresh.transitions[0].reason == "false positive"


def test_alert_transition_to_same_status_is_rejected(
    client: FlaskClient, app: Flask, admin: User
) -> None:
    alert, _ = _seed(client, app)
    login_as_admin(client, admin)

    response = client.post(
        f"/api/v1/alerts/{alert.id}/transitions",
        json={"status": "open"},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "alert_status_unchanged"


def test_alert_transition_validates_status_enum(
    client: FlaskClient, app: Flask, admin: User
) -> None:
    alert, _ = _seed(client, app)
    login_as_admin(client, admin)

    response = client.post(
        f"/api/v1/alerts/{alert.id}/transitions",
        json={"status": "purple"},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_alert_not_found(client: FlaskClient, admin: User) -> None:
    login_as_admin(client, admin)
    response = client.get("/api/v1/alerts/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "alert_not_found"


def test_admin_can_update_rule(client: FlaskClient, app: Flask, admin: User) -> None:
    _, rule = _seed(client, app)
    login_as_admin(client, admin)

    response = client.patch(
        f"/api/v1/rules/{rule.id}",
        json={"enabled": False, "severity": "critical"},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 200
    body = response.get_json()["rule"]
    assert body["enabled"] is False
    assert body["severity"] == "critical"


def test_rule_update_requires_change(client: FlaskClient, app: Flask, admin: User) -> None:
    _, rule = _seed(client, app)
    login_as_admin(client, admin)

    response = client.patch(
        f"/api/v1/rules/{rule.id}",
        json={},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_rule_not_found(client: FlaskClient, admin: User) -> None:
    login_as_admin(client, admin)
    response = client.patch(
        "/api/v1/rules/00000000-0000-0000-0000-000000000000",
        json={"enabled": False},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "rule_not_found"
