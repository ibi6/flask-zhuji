from __future__ import annotations

import hashlib
import hmac

from hostguard_agent.signing import build_signature, signed_headers


def test_build_signature_matches_shared_contract() -> None:
    body = b'{"batch_id":"123"}'
    canonical = (
        "1700000000\nnonce-1\nPOST\n/api/v1/agent/batches\n" + hashlib.sha256(body).hexdigest()
    )

    result = build_signature(
        secret="top-secret",
        timestamp="1700000000",
        nonce="nonce-1",
        method="post",
        path="/api/v1/agent/batches",
        body=body,
    )

    assert result == hmac.new(b"top-secret", canonical.encode(), hashlib.sha256).hexdigest()


def test_signed_headers_include_agent_identity_and_lowercase_hex_signature() -> None:
    headers = signed_headers(
        agent_id="525d314e-cbd4-42d4-9de0-1ed717a5d82a",
        secret="secret",
        method="GET",
        path="/api/v1/agent/policy",
        body=b"",
        timestamp="1700000000",
        nonce="nonce-2",
    )

    assert headers["X-HG-Agent-Id"] == "525d314e-cbd4-42d4-9de0-1ed717a5d82a"
    assert headers["X-HG-Timestamp"] == "1700000000"
    assert headers["X-HG-Nonce"] == "nonce-2"
    assert len(headers["X-HG-Signature"]) == 64
    assert headers["X-HG-Signature"].isalnum()
    assert headers["X-HG-Signature"] == headers["X-HG-Signature"].lower()
