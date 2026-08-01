"""Signed HTTP client for the HostGuard agent API.

Implements the shared signing conventions (``contracts/conventions.md``):

* Every request carries ``X-HG-Agent-Id``, ``X-HG-Timestamp``,
  ``X-HG-Nonce`` and ``X-HG-Signature``.
* The signature is HMAC-SHA256 over
  ``timestamp\\nnonce\\nMETHOD\\n/path\\nsha256_hex(raw_body)``.

The raw request body bytes are hashed exactly as transmitted, so JSON
payloads are serialized deterministically before signing.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from .signing import signed_headers

__all__ = ["SignedHTTPClient", "HttpClient", "APIClientError"]


class APIClientError(Exception):
    """Raised when an API request fails at the transport level."""


class HttpClient(Protocol):
    """Minimal protocol over the agent API used by the orchestrator."""

    def post_json(self, path: str, payload: dict[str, Any]) -> httpx.Response: ...

    def get(self, path: str) -> httpx.Response: ...

    def close(self) -> None: ...


def _default_clock() -> str:
    """Return the current UTC time in ISO-8601 with a trailing ``Z``.

    The shared conventions (``contracts/conventions.md``) require every
    timestamp to be UTC ISO-8601; the server parses the header with
    ``datetime.fromisoformat`` and rejects epoch integers.
    """
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _default_nonce() -> str:
    return uuid.uuid4().hex


def _encode_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


class SignedHTTPClient:
    """HTTP client that signs every request with the agent secret."""

    def __init__(
        self,
        *,
        base_url: str,
        agent_id: str,
        secret: str,
        timeout: float = 15.0,
        verify: bool = True,
        clock: Callable[[], str] | None = None,
        nonce_factory: Callable[[], str] | None = None,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._agent_id = agent_id
        self._secret = secret
        self._clock = clock or _default_clock
        self._nonce_factory = nonce_factory or _default_nonce
        if client is not None:
            self._client = client
        else:
            self._client = httpx.Client(
                base_url=self._base_url,
                timeout=timeout,
                verify=verify,
                transport=transport,
            )

    def request(self, method: str, path: str, body: bytes = b"") -> httpx.Response:
        """Send a signed request and return the raw response."""
        if not path.startswith("/"):
            raise ValueError(f"path must start with '/', got {path!r}")
        timestamp = self._clock()
        nonce = self._nonce_factory()
        headers = signed_headers(
            agent_id=self._agent_id,
            secret=self._secret,
            method=method,
            path=path,
            body=body,
            timestamp=timestamp,
            nonce=nonce,
        )
        try:
            return self._client.request(
                method, self._base_url + path, content=body, headers=headers
            )
        except httpx.HTTPError as exc:
            raise APIClientError(f"{method} {path} failed: {exc}") from exc

    def post_json(self, path: str, payload: dict[str, Any]) -> httpx.Response:
        body = _encode_json(payload)
        return self.request("POST", path, body=body)

    def get(self, path: str) -> httpx.Response:
        return self.request("GET", path, body=b"")

    def close(self) -> None:
        self._client.close()
