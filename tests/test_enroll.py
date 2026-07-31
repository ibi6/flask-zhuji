"""Enrollment flow against the agent API."""

from __future__ import annotations

import httpx
import pytest

from hostguard_agent.credentials import AgentCredentials
from hostguard_agent.enroll import ENROLL_PATH, EnrollmentError, enroll


def _client_for(status: int, body: dict) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == ENROLL_PATH
        assert request.headers["content-type"] == "application/json"
        return httpx.Response(status, json=body)

    return httpx.Client(base_url="https://hg.example", transport=httpx.MockTransport(handler))


def test_enroll_returns_credentials_on_201() -> None:
    credentials = enroll(
        "https://hg.example",
        "one-time-token",
        client=_client_for(201, {"agent_id": "agent-1", "secret": "secret-1"}),
    )
    assert credentials == AgentCredentials(agent_id="agent-1", secret="secret-1")


def test_enroll_rejection_raises_enrollment_error() -> None:
    with pytest.raises(EnrollmentError, match="401"):
        enroll(
            "https://hg.example",
            "bad-token",
            client=_client_for(401, {"error": {"code": "invalid_token"}}),
        )


def test_enroll_missing_fields_raises() -> None:
    with pytest.raises(EnrollmentError, match="agent_id"):
        enroll(
            "https://hg.example",
            "token",
            client=_client_for(201, {"agent_id": "x"}),
        )


def test_enroll_empty_token_raises() -> None:
    with pytest.raises(EnrollmentError, match="token"):
        enroll("https://hg.example", "")
