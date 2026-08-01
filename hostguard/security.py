from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, request
from sqlalchemy import delete

from .errors import ApiError
from .extensions import db
from .models import AgentNonce, utcnow

AGENT_KEY_SALT = b"hostguard-agent-secret-v1"
AGENT_CLOCK_SKEW_SECONDS = 300
AGENT_NONCE_TTL_SECONDS = 600

CSRF_COOKIE = "hostguard_csrf_token"
SESSION_COOKIE = "hostguard_session"


# --- generic token helpers -------------------------------------------------


def generate_token(byte_length: int = 32) -> str:
    return secrets.token_urlsafe(byte_length)


def hash_token(token: str) -> str:
    """Deterministic digest used when a server-side copy of a token is stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)


# --- agent secret encryption ------------------------------------------------


@lru_cache(maxsize=1)
def _agent_fernet(secret_key: str) -> Fernet:
    derived = hashlib.pbkdf2_hmac(
        "sha256", secret_key.encode("utf-8"), AGENT_KEY_SALT, 100_000, dklen=32
    )
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_agent_secret(plaintext: bytes) -> bytes:
    return _agent_fernet(current_app.config["SECRET_KEY"]).encrypt(plaintext)


def decrypt_agent_secret(token: bytes) -> bytes:
    try:
        return _agent_fernet(current_app.config["SECRET_KEY"]).decrypt(token)
    except InvalidToken as exc:
        raise ApiError("agent_credential_invalid", "The agent credential is invalid.", 403) from exc


# --- HMAC request signing ----------------------------------------------------


def agent_canonical_message(
    timestamp: str, nonce: str, method: str, path: str, raw_body: bytes
) -> str:
    body_digest = hashlib.sha256(raw_body).hexdigest()
    return f"{timestamp}\n{nonce}\n{method}\n{path}\n{body_digest}"


def sign_message(secret: bytes, message: str) -> str:
    return hmac.new(secret, message.encode("utf-8"), hashlib.sha256).hexdigest()


def parse_agent_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError("agent_timestamp_invalid", "The agent timestamp is invalid.", 403) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _delete_expired_nonces() -> None:
    db.session.execute(delete(AgentNonce).where(AgentNonce.expires_at < utcnow()))


def consume_agent_nonce(agent_id: str, nonce: str) -> None:
    """Refuse replayed nonces; retain a nonce for ten minutes after the request."""
    _delete_expired_nonces()
    if not nonce or len(nonce) > 128:
        raise ApiError("agent_nonce_invalid", "The agent nonce is invalid.", 403)
    existing = AgentNonce.query.filter_by(nonce=nonce).first()
    if existing is not None:
        raise ApiError(
            "agent_nonce_replay", "The agent nonce has already been used.", 403
        )
    db.session.add(
        AgentNonce(
            agent_id=agent_id,
            nonce=nonce,
            expires_at=utcnow() + timedelta(seconds=AGENT_NONCE_TTL_SECONDS),
        )
    )


def verify_agent_signature(secret: bytes, raw_body: bytes) -> tuple[str, str]:
    """Validate the HMAC-SHA256 request signature and clock skew.

    Returns ``(timestamp, nonce)``; raises :class:`ApiError` on any failure.
    """
    agent_id = request.headers.get("X-HG-Agent-Id")
    timestamp = request.headers.get("X-HG-Timestamp")
    nonce = request.headers.get("X-HG-Nonce")
    signature = request.headers.get("X-HG-Signature")
    if not agent_id or not timestamp or not nonce or not signature:
        raise ApiError(
            "agent_signature_required",
            "The request is missing agent signing headers.",
            401,
        )

    if not _valid_uuid(agent_id):
        raise ApiError("agent_id_invalid", "The agent id is invalid.", 403)

    sent_at = parse_agent_timestamp(timestamp)
    now = utcnow()
    if abs((now - sent_at).total_seconds()) > AGENT_CLOCK_SKEW_SECONDS:
        raise ApiError("agent_timestamp_invalid", "The agent timestamp is out of range.", 403)

    message = agent_canonical_message(timestamp, nonce, request.method, request.path, raw_body)
    expected = sign_message(secret, message)
    if not constant_time_equal(signature, expected):
        raise ApiError("invalid_signature", "The request signature is invalid.", 403)
    return timestamp, nonce


def _valid_uuid(value: str) -> bool:
    try:
        uuid_obj = UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return str(uuid_obj) == value


# --- CSRF double-submit cookie -----------------------------------------------


def issue_csrf_token() -> tuple[str, int]:
    """Return ``(token, max_age_seconds)``; the cookie carries the same token."""
    token = generate_token()
    max_age = int(current_app.config["CSRF_TTL_SECONDS"])
    return token, max_age


def require_csrf() -> None:
    """Enforce the double-submit CSRF check for browser mutating requests."""
    sent = request.headers.get("X-CSRF-Token", "")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    if not sent or not cookie or not constant_time_equal(sent, cookie):
        raise ApiError(
            "csrf_required", "A valid CSRF token is required for this request.", 403
        )
