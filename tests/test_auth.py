from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient

from hostguard.extensions import db
from hostguard.models import User, WebSession

from .conftest import csrf_token, login


def test_login_requires_csrf(client: FlaskClient, admin: User) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": admin.username, "password": "Correct-Horse-Battery-42"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "csrf_required"


def test_login_sets_database_backed_secure_cookie_and_returns_me(
    client: FlaskClient, app: Flask, admin: User
) -> None:
    login(client, admin.username, "Correct-Horse-Battery-42")

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.get_json()["user"] == {
        "id": admin.id,
        "username": "admin",
        "email": "admin@example.com",
        "role": "admin",
        "is_active": True,
    }

    cookie = next(
        cookie for cookie in client._cookies.values() if cookie.key == "hostguard_session"
    )
    assert cookie.http_only is True
    assert cookie.same_site == "Strict"
    assert cookie.value

    with app.app_context():
        assert WebSession.query.filter_by(user_id=admin.id, revoked_at=None).count() == 1
        session = WebSession.query.filter_by(user_id=admin.id).one()
        assert session.token_hash != cookie.value


def test_login_rejects_invalid_credentials_without_leaking_identity(
    client: FlaskClient, admin: User
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": admin.username, "password": "not-the-password"},
        headers={"X-CSRF-Token": csrf_token(client)},
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_credentials"
    body = response.get_data(as_text=True).lower()
    assert "not-the-password" not in body
    assert "correct-horse-battery-42" not in body


def test_login_for_unknown_user_reports_same_error(client: FlaskClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "ghost", "password": "whatever-password"},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_credentials"


def test_me_requires_authentication(client: FlaskClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_revokes_session(client: FlaskClient, app: Flask, admin: User) -> None:
    login(client, admin.username, "Correct-Horse-Battery-42")

    response = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_token(client)})

    assert response.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    with app.app_context():
        assert WebSession.query.filter_by(user_id=admin.id, revoked_at=None).count() == 0


def test_login_is_rate_limited(client: FlaskClient, admin: User) -> None:
    statuses = []
    for _ in range(6):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": admin.username, "password": "wrong-password"},
            headers={"X-CSRF-Token": csrf_token(client)},
        )
        statuses.append(response.status_code)

    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[5] == 429
    assert response.get_json()["error"]["code"] == "rate_limit_exceeded"


def test_login_rejects_unknown_fields(client: FlaskClient, admin: User) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": admin.username,
            "password": "Correct-Horse-Battery-42",
            "role": "admin",
        },
        headers={"X-CSRF-Token": csrf_token(client)},
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_inactive_user_cannot_login(client: FlaskClient, app: Flask, admin: User) -> None:
    with app.app_context():
        user = db.session.get(User, admin.id)
        assert user is not None
        user.is_active = False
        db.session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"username": admin.username, "password": "Correct-Horse-Battery-42"},
        headers={"X-CSRF-Token": csrf_token(client)},
    )

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_credentials"
