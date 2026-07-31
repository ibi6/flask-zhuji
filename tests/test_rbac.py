from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient

from hostguard.extensions import db
from hostguard.models import Alert, DetectionRule, User

from .conftest import csrf_token, login


def _create_role_user(app: Flask, role: str) -> User:
    with app.app_context():
        user = User(username=f"user-{role}", email=f"{role}@example.com", role=role)
        user.set_password("Role-Password-42")
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)
        db.session.expunge(user)
        return user


def _seed_alert(app: Flask) -> Alert:
    with app.app_context():
        alert = Alert(
            title="Suspicious login",
            severity="high",
            status="open",
            description="Repeated failed logins detected",
        )
        db.session.add(alert)
        db.session.commit()
        db.session.refresh(alert)
        db.session.expunge(alert)
        return alert


def _seed_rule(app: Flask) -> DetectionRule:
    with app.app_context():
        rule = DetectionRule(
            name="brute-force",
            rule_type="signature",
            enabled=True,
            severity="medium",
            criteria={"threshold": 5},
        )
        db.session.add(rule)
        db.session.commit()
        db.session.refresh(rule)
        db.session.expunge(rule)
        return rule


def test_analyst_can_transition_alerts(client: FlaskClient, app: Flask) -> None:
    analyst = _create_role_user(app, "analyst")
    alert = _seed_alert(app)
    login(client, analyst.username, "Role-Password-42")

    response = client.post(
        f"/api/v1/alerts/{alert.id}/transitions",
        json={"status": "investigating", "reason": "checking logs"},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 200
    assert response.get_json()["alert"]["status"] == "investigating"
    with app.app_context():
        fresh = db.session.get(Alert, alert.id)
        assert fresh is not None
        assert len(fresh.transitions) == 1


def test_viewer_cannot_transition_alerts(client: FlaskClient, app: Flask) -> None:
    viewer = _create_role_user(app, "viewer")
    alert = _seed_alert(app)
    login(client, viewer.username, "Role-Password-42")

    response = client.post(
        f"/api/v1/alerts/{alert.id}/transitions",
        json={"status": "resolved"},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"


def test_analyst_cannot_update_rules(client: FlaskClient, app: Flask) -> None:
    analyst = _create_role_user(app, "analyst")
    rule = _seed_rule(app)
    login(client, analyst.username, "Role-Password-42")

    response = client.patch(
        f"/api/v1/rules/{rule.id}",
        json={"enabled": False},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"


def test_viewer_can_read_alert_and_rule_lists(
    client: FlaskClient, app: Flask
) -> None:
    viewer = _create_role_user(app, "viewer")
    _seed_alert(app)
    _seed_rule(app)
    login(client, viewer.username, "Role-Password-42")

    assert client.get("/api/v1/alerts").status_code == 200
    assert client.get("/api/v1/rules").status_code == 200
    assert client.get("/api/v1/dashboard/summary").status_code == 200
    assert client.get("/api/v1/audit").status_code == 200


def test_analyst_can_create_reports(client: FlaskClient, app: Flask) -> None:
    analyst = _create_role_user(app, "analyst")
    login(client, analyst.username, "Role-Password-42")

    response = client.post(
        "/api/v1/reports",
        json={"report_type": "daily_summary", "parameters": {"scope": "all"}},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 202
    assert response.get_json()["status"] == "pending"


def test_viewer_cannot_create_reports(client: FlaskClient, app: Flask) -> None:
    viewer = _create_role_user(app, "viewer")
    login(client, viewer.username, "Role-Password-42")

    response = client.post(
        "/api/v1/reports",
        json={"report_type": "daily_summary"},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"


def test_unauthenticated_requests_get_401(client: FlaskClient) -> None:
    assert client.get("/api/v1/hosts").status_code == 401
    assert client.get("/api/v1/alerts").status_code == 401
    assert client.get("/api/v1/dashboard/summary").status_code == 401
    body = client.get("/api/v1/hosts").get_json()["error"]
    assert body["code"] == "authentication_required"
