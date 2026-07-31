"""One-time agent enrollment against the HostGuard backend.

POST ``/api/v1/agent/enroll`` exchanges a one-time enrollment token for
``(agent_id, secret)`` credentials. The request is not HMAC-signed: the
agent has no identity yet, so the one-time token itself is the credential
and transport security (HTTPS) protects the exchange. The server returns
the secret exactly once, so the caller is responsible for persisting it
immediately via a credential store.
"""

from __future__ import annotations

from typing import Any

import httpx

from .credentials import AgentCredentials

__all__ = ["EnrollmentError", "enroll"]

ENROLL_PATH = "/api/v1/agent/enroll"


class EnrollmentError(Exception):
    """Raised when enrollment fails for any reason."""


def enroll(
    server_url: str,
    token: str,
    *,
    timeout: float = 15.0,
    verify: bool = True,
    client: httpx.Client | None = None,
) -> AgentCredentials:
    """Enroll with a one-time token and return the issued credentials."""
    if not token:
        raise EnrollmentError("enrollment token must not be empty")
    owns_client = client is None
    http = client or httpx.Client(base_url=server_url.rstrip("/"), timeout=timeout, verify=verify)
    try:
        try:
            response = http.post(ENROLL_PATH, json={"token": token})
        except httpx.HTTPError as exc:
            raise EnrollmentError(f"enroll request failed: {exc}") from exc
        if response.status_code not in (200, 201):
            raise EnrollmentError(
                f"enroll rejected with HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            data: Any = response.json()
        except ValueError as exc:
            raise EnrollmentError("enroll response was not valid JSON") from exc
        return _extract_credentials(data)
    finally:
        if owns_client:
            http.close()


def _extract_credentials(data: Any) -> AgentCredentials:
    if not isinstance(data, dict):
        raise EnrollmentError("enroll response must be a JSON object")
    agent_id = data.get("agent_id")
    secret = data.get("secret")
    if agent_id is None or secret is None:
        raise EnrollmentError("enroll response missing agent_id or secret")
    if not isinstance(agent_id, str) or not isinstance(secret, str):
        raise EnrollmentError("enroll response agent_id/secret must be strings")
    return AgentCredentials(agent_id=agent_id, secret=secret)
