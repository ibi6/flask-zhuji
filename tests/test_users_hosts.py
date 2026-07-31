from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient

from hostguard.extensions import db
from hostguard.models import Host, User

from .conftest import csrf_token, login, login_as_admin


def _create_user(app: Flask, username: str, role: str) -> User:
    with app.app_context():
        user = User(username=username, email=f"{username}@example.com", role=role)
        user.set_password("Viewer-Password-42")
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)
        db.session.expunge(user)
        return user


def test_viewer_can_list_hosts_but_cannot_manage_users(
    client: FlaskClient, app: Flask
) -> None:
    viewer = _create_user(app, "viewer", "viewer")
    with app.app_context():
        db.session.add(
            Host(hostname="workstation-01", os="windows", source="real", status="online")
        )
        db.session.commit()

    login(client, viewer.username, "Viewer-Password-42")

    hosts = client.get("/api/v1/hosts")
    users = client.get("/api/v1/users")
    assert hosts.status_code == 200
    assert hosts.get_json()["total"] == 1
    assert hosts.get_json()["items"][0]["hostname"] == "workstation-01"
    assert users.status_code == 403
    assert users.get_json()["error"]["code"] == "forbidden"


def test_admin_can_create_and_deactivate_user(
    client: FlaskClient, app: Flask, admin: User
) -> None:
    login_as_admin(client, admin)
    created = client.post(
        "/api/v1/users",
        json={
            "username": "analyst",
            "email": "analyst@example.com",
            "password": "Analyst-Password-42",
            "role": "analyst",
        },
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert created.status_code == 201
    user_id = created.get_json()["user"]["id"]

    deactivated = client.patch(
        f"/api/v1/users/{user_id}",
        json={"is_active": False},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert deactivated.status_code == 200
    assert deactivated.get_json()["user"]["is_active"] is False

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user is not None
        assert user.is_active is False


def test_admin_cannot_deactivate_own_account(client: FlaskClient, admin: User) -> None:
    login_as_admin(client, admin)

    response = client.patch(
        f"/api/v1/users/{admin.id}",
        json={"is_active": False},
        headers={"X-CSRF-Token": csrf_token(client)},
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "self_deactivation_forbidden"


def test_admin_cannot_delete_own_account(client: FlaskClient, admin: User) -> None:
    login_as_admin(client, admin)

    response = client.delete(
        f"/api/v1/users/{admin.id}",
        headers={"X-CSRF-Token": csrf_token(client)},
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "self_deletion_forbidden"


def test_admin_cannot_demote_own_role(client: FlaskClient, admin: User) -> None:
    login_as_admin(client, admin)

    response = client.patch(
        f"/api/v1/users/{admin.id}",
        json={"role": "viewer"},
        headers={"X-CSRF-Token": csrf_token(client)},
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "self_demotion_forbidden"


def test_admin_can_delete_other_user(client: FlaskClient, app: Flask, admin: User) -> None:
    other = _create_user(app, "someone", "viewer")
    login_as_admin(client, admin)

    response = client.delete(
        f"/api/v1/users/{other.id}",
        headers={"X-CSRF-Token": csrf_token(client)},
    )

    assert response.status_code == 204
    with app.app_context():
        user = db.session.get(User, other.id)
        assert user is not None
        assert user.is_active is False


def test_user_creation_validates_role_and_duplicate_username(
    client: FlaskClient, admin: User
) -> None:
    login_as_admin(client, admin)

    invalid = client.post(
        "/api/v1/users",
        json={
            "username": "someone",
            "email": "someone@example.com",
            "password": "Someone-Password-42",
            "role": "superuser",
        },
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    duplicate = client.post(
        "/api/v1/users",
        json={
            "username": admin.username.upper(),
            "email": "another@example.com",
            "password": "Someone-Password-42",
            "role": "viewer",
        },
        headers={"X-CSRF-Token": csrf_token(client)},
    )

    assert invalid.status_code == 422
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"]["code"] == "user_already_exists"


def test_user_creation_rejects_weak_password(client: FlaskClient, admin: User) -> None:
    login_as_admin(client, admin)
    response = client.post(
        "/api/v1/users",
        json={
            "username": "weakpass",
            "email": "weak@example.com",
            "password": "alllowercase",
            "role": "viewer",
        },
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_update_unknown_user_returns_404(client: FlaskClient, admin: User) -> None:
    login_as_admin(client, admin)
    response = client.patch(
        "/api/v1/users/00000000-0000-0000-0000-000000000000",
        json={"is_active": False},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "user_not_found"


def test_user_list_is_paginated(client: FlaskClient, app: Flask, admin: User) -> None:
    for index in range(5):
        _create_user(app, f"user{index}", "viewer")
    login_as_admin(client, admin)

    response = client.get("/api/v1/users?page=1&page_size=3")
    assert response.status_code == 200
    body = response.get_json()
    assert body["page"] == 1
    assert body["page_size"] == 3
    assert body["total"] == 6
    assert len(body["items"]) == 3
