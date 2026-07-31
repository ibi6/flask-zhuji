from __future__ import annotations

import httpx

from hostguard_agent.http_client import APIClientError, SignedHTTPClient
from hostguard_agent.signing import build_signature


def test_post_json_sends_signed_headers_and_body() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content
        return httpx.Response(202, json={"status": "accepted"})

    client = SignedHTTPClient(
        base_url="https://hg.example",
        agent_id="agent-1",
        secret="top-secret",
        clock=lambda: "1700000000",
        nonce_factory=lambda: "nonce-1",
        transport=httpx.MockTransport(handler),
    )
    payload = {"batch_id": "batch-1", "value": 42}
    response = client.post_json("/api/v1/agent/batches", payload)

    headers = captured["headers"]
    assert headers["x-hg-agent-id"] == "agent-1"
    assert headers["x-hg-timestamp"] == "1700000000"
    assert headers["x-hg-nonce"] == "nonce-1"
    body = captured["body"]
    assert isinstance(body, bytes)
    expected = build_signature(
        secret="top-secret",
        timestamp="1700000000",
        nonce="nonce-1",
        method="POST",
        path="/api/v1/agent/batches",
        body=body,
    )
    assert headers["x-hg-signature"] == expected
    assert response.status_code == 202


def test_get_signs_empty_body_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(200, json={"revision": 1})

    client = SignedHTTPClient(
        base_url="https://hg.example",
        agent_id="agent-1",
        secret="s",
        transport=httpx.MockTransport(handler),
    )
    client.get("/api/v1/agent/policy")
    assert captured["body"] == b""


def test_transport_error_becomes_api_client_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = SignedHTTPClient(
        base_url="https://hg.example",
        agent_id="a",
        secret="s",
        transport=httpx.MockTransport(handler),
    )
    try:
        client.get("/api/v1/agent/policy")
    except APIClientError as exc:
        assert "GET /api/v1/agent/policy failed" in str(exc)
    else:
        raise AssertionError("expected APIClientError")


def test_path_must_start_with_slash() -> None:
    client = SignedHTTPClient(
        base_url="https://hg.example",
        agent_id="a",
        secret="s",
        transport=httpx.MockTransport(lambda r: httpx.Response(200)),
    )
    try:
        client.get("api/v1/agent/policy")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for relative path")


def test_json_response_helpers() -> None:
    client = SignedHTTPClient(
        base_url="https://hg.example",
        agent_id="a",
        secret="s",
        transport=httpx.MockTransport(lambda r: httpx.Response(202, json={"ok": True})),
    )
    response = client.post_json("/api/v1/agent/batches", {"a": 1})
    assert response.json() == {"ok": True}
