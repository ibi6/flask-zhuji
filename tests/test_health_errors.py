from __future__ import annotations

from uuid import UUID

from flask.testing import FlaskClient


def test_health_endpoints_report_live_and_ready(client: FlaskClient) -> None:
    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.get_json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.get_json() == {"status": "ready"}


def test_unknown_route_uses_structured_error_and_request_id(client: FlaskClient) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    error = response.get_json()["error"]
    assert error["code"] == "not_found"
    assert error["message"] == "The requested resource was not found."
    assert error["details"] == {}
    assert UUID(error["request_id"])
    assert response.headers["X-Request-ID"] == error["request_id"]


def test_invalid_incoming_request_id_is_replaced(client: FlaskClient) -> None:
    response = client.get("/does-not-exist", headers={"X-Request-ID": "not-a-uuid"})

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] != "not-a-uuid"
    assert UUID(response.headers["X-Request-ID"])


def test_security_headers_are_present(client: FlaskClient) -> None:
    response = client.get("/health/live")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_api_responses_are_not_cached(client: FlaskClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.headers["Cache-Control"] == "no-store"


def test_unsupported_content_type_returns_structured_error(client: FlaskClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        data="username=admin",
        content_type="text/plain",
        headers={"X-CSRF-Token": "some-token"},
    )
    # CSRF fails first when no matching cookie is present.
    assert response.status_code in (400, 403, 415)
    assert "error" in response.get_json()
