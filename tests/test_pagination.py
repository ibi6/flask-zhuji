from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient

from hostguard.extensions import db
from hostguard.models import User

from .conftest import login_as_admin


def _seed_hosts(app: Flask, count: int) -> None:
    from hostguard.models import Host

    with app.app_context():
        for index in range(count):
            db.session.add(
                Host(hostname=f"host-{index:02d}", os="linux", source="real", status="online")
            )
        db.session.commit()


def test_pagination_envelope_shape(client: FlaskClient, app: Flask, admin: User) -> None:
    _seed_hosts(app, 3)
    login_as_admin(client, admin)

    response = client.get("/api/v1/hosts?page=1&page_size=2")
    assert response.status_code == 200
    body = response.get_json()
    assert set(body.keys()) == {"items", "page", "page_size", "total"}
    assert len(body["items"]) == 2
    assert body["total"] == 3


def test_pagination_out_of_range_page_returns_empty_items(
    client: FlaskClient, app: Flask, admin: User
) -> None:
    _seed_hosts(app, 3)
    login_as_admin(client, admin)

    response = client.get("/api/v1/hosts?page=99&page_size=20")
    body = response.get_json()
    assert body["items"] == []
    assert body["total"] == 3


def test_pagination_validates_page_and_page_size(
    client: FlaskClient, app: Flask, admin: User
) -> None:
    login_as_admin(client, admin)

    for query in ("page=0", "page_size=0", "page_size=1000", "page=abc"):
        response = client.get(f"/api/v1/hosts?{query}")
        assert response.status_code == 422, query
        assert response.get_json()["error"]["code"] == "validation_error"


def test_hosts_list_requires_auth_without_session(
    client: FlaskClient, app: Flask
) -> None:
    _seed_hosts(app, 1)
    response = client.get("/api/v1/hosts")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "authentication_required"


def test_users_list_pagination(client: FlaskClient, app: Flask, admin: User) -> None:
    with app.app_context():
        for index in range(3):
            user = User(
                username=f"extra{index}", email=f"extra{index}@example.com", role="viewer"
            )
            user.set_password("Extra-Password-42")
            db.session.add(user)
        db.session.commit()
    login_as_admin(client, admin)

    response = client.get("/api/v1/users?page_size=2")
    body = response.get_json()
    assert body["total"] == 4
    assert len(body["items"]) == 2
