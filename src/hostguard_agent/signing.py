"""Request signing per the HostGuard shared conventions.

Conventions (see ``contracts/conventions.md``):

* Signed requests include ``X-HG-Agent-Id``, ``X-HG-Timestamp``,
  ``X-HG-Nonce`` and ``X-HG-Signature``.
* The lowercase hex signature is HMAC-SHA256 over::

    timestamp\\nnonce\\nMETHOD\\n/path\\nsha256_hex(raw_body)
"""

from __future__ import annotations

import hashlib
import hmac

__all__ = ["build_signature", "signed_headers"]

#: Header names mandated by the shared conventions.
HEADER_AGENT_ID = "X-HG-Agent-Id"
HEADER_TIMESTAMP = "X-HG-Timestamp"
HEADER_NONCE = "X-HG-Nonce"
HEADER_SIGNATURE = "X-HG-Signature"


def _secret_bytes(secret: str) -> bytes:
    """Return the raw key bytes for HMAC signing.

    The enrollment endpoint returns the agent secret as a lowercase hex
    string; the server derives the HMAC key from the raw 32 bytes, so the
    agent must convert the hex back to bytes before signing. Plain-string
    secrets (used in tests) fall back to UTF-8 encoding.
    """
    try:
        decoded = bytes.fromhex(secret)
    except ValueError:
        return secret.encode("utf-8")
    if len(decoded) == 32:
        return decoded
    return secret.encode("utf-8")


def build_signature(
    *,
    secret: str,
    timestamp: str,
    nonce: str,
    method: str,
    path: str,
    body: bytes,
) -> str:
    """Return the HMAC-SHA256 signature for a request.

    ``method`` is uppercased and ``path`` is used verbatim. The body is
    hashed with SHA-256 and embedded as lowercase hex.
    """
    body_digest = hashlib.sha256(body).hexdigest()
    canonical = "\n".join(
        (
            timestamp,
            nonce,
            method.upper(),
            path,
            body_digest,
        )
    )
    return hmac.new(
        _secret_bytes(secret), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def signed_headers(
    *,
    agent_id: str,
    secret: str,
    method: str,
    path: str,
    body: bytes,
    timestamp: str,
    nonce: str,
) -> dict[str, str]:
    """Return the full set of signing headers for a request."""
    signature = build_signature(
        secret=secret,
        timestamp=timestamp,
        nonce=nonce,
        method=method,
        path=path,
        body=body,
    )
    return {
        HEADER_AGENT_ID: agent_id,
        HEADER_TIMESTAMP: timestamp,
        HEADER_NONCE: nonce,
        HEADER_SIGNATURE: signature,
    }
