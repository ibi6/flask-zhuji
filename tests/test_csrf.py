from __future__ import annotations

from flask.testing import FlaskClient

from .conftest import csrf_token


def test_csrf_endpoint_returns_token_and_sets_cookie(client: FlaskClient) -> None:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    token = response.get_json()["csrf_token"]
    assert token
    cookie = next(
        cookie for cookie in client._cookies.values() if cookie.key == "hostguard_csrf_token"
    )
    assert cookie.value == token
    assert cookie.http_only is True
    assert cookie.same_site == "Strict"


def test_mutating_request_without_csrf_is_rejected(client: FlaskClient) -> None:
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "csrf_required"


def test_mutating_request_with_wrong_csrf_is_rejected(client: FlaskClient) -> None:
    response = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": "not-the-right-token"},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "csrf_required"


def test_csrf_token_is_accepted_once_cookie_is_present(client: FlaskClient) -> None:
    response = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code in (204, 401)


def test_read_requests_do_not_require_csrf(client: FlaskClient) -> None:
    assert client.get("/api/v1/hosts").status_code == 401  # not 403
    assert client.get("/api/v1/auth/csrf").status_code == 200


def test_agent_endpoints_are_exempt_from_csrf(client: FlaskClient) -> None:
    response = client.post("/api/v1/agent/enroll", json={"token": "x" * 20})
    assert response.status_code != 403
    assert response.status_code in (400, 422)
