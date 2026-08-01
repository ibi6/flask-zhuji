from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient

from hostguard.models import AuditLog, User

from .conftest import csrf_token, login_as_admin


def test_login_and_user_actions_are_audited(
    client: FlaskClient, app: Flask, admin: User
) -> None:
    login_as_admin(client, admin)
    client.post(
        "/api/v1/users",
        json={
            "username": "newbie",
            "email": "newbie@example.com",
            "password": "Newbie-Password-42",
            "role": "viewer",
        },
        headers={"X-CSRF-Token": csrf_token(client)},
    )

    response = client.get("/api/v1/audit")
    assert response.status_code == 200
    body = response.get_json()
    actions = {item["action"] for item in body["items"]}
    assert "auth.login" in actions
    assert "user.create" in actions
    assert body["total"] >= 2


def test_audit_can_filter_by_action(client: FlaskClient, app: Flask, admin: User) -> None:
    login_as_admin(client, admin)

    response = client.get("/api/v1/audit?action=auth.login")
    body = response.get_json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "auth.login"
    assert body["items"][0]["actor_username"] == "admin"


def test_audit_is_paginated(client: FlaskClient, app: Flask, admin: User) -> None:
    login_as_admin(client, admin)
    for index in range(4):
        client.patch(
            f"/api/v1/users/{admin.id}",
            json={"email": f"admin{index}@example.com"},
            headers={"X-CSRF-Token": csrf_token(client)},
        )

    response = client.get("/api/v1/audit?page_size=2&page=1")
    body = response.get_json()
    assert body["total"] == 5  # 1 login + 4 updates
    assert len(body["items"]) == 2

    with app.app_context():
        assert AuditLog.query.filter_by(action="user.update").count() == 4
