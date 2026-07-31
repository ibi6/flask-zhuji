from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from argon2 import PasswordHasher
from flask import Flask
from flask.testing import FlaskClient

from hostguard import create_app
from hostguard.extensions import db
from hostguard.models import EnrollmentToken, User, utcnow
from hostguard.security import hash_token

TEST_SECRET_KEY = "test-secret-key-with-at-least-32-characters"


@pytest.fixture(autouse=True)
def _fast_password_hasher(monkeypatch: pytest.MonkeyPatch) -> None:
    """Speed up Argon2 for tests without changing production parameters."""
    fast = PasswordHasher(time_cost=2, memory_cost=2048, parallelism=1)
    monkeypatch.setattr("hostguard.models.password_hasher", fast)


@pytest.fixture()
def app(tmp_path: Path) -> Iterator[Flask]:
    database_path = tmp_path / "hostguard-test.db"
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
            "SECRET_KEY": TEST_SECRET_KEY,
            "SESSION_COOKIE_SECURE": False,
            "RATELIMIT_STORAGE_URI": "memory://",
            "LOGIN_RATE_LIMIT": "5 per minute",
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture()
def admin(app: Flask) -> User:
    with app.app_context():
        user = User(username="admin", email="admin@example.com", role="admin")
        user.set_password("Correct-Horse-Battery-42")
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)
        db.session.expunge(user)
        return user


def csrf_token(client: FlaskClient) -> str:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return response.get_json()["csrf_token"]


def login(client: FlaskClient, username: str, password: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 200, response.get_json()


def login_as_admin(client: FlaskClient, admin: User) -> None:
    login(client, admin.username, "Correct-Horse-Battery-42")


def create_enrollment_token(app: Flask, expires_hours: int = 24) -> str:
    """Create a raw enrollment token in the database; returns the plaintext token."""
    from hostguard.security import generate_token

    token = generate_token()
    with app.app_context():
        db.session.add(
            EnrollmentToken(
                token_hash=hash_token(token),
                expires_at=utcnow() + timedelta(hours=expires_hours),
            )
        )
        db.session.commit()
    return token


def enroll_agent(client: FlaskClient, token: str, hostname: str = "agent-01") -> dict[str, str]:
    response = client.post(
        "/api/v1/agent/enroll",
        json={
            "token": token,
            "hostname": hostname,
            "os": "windows",
            "os_version": "11",
            "architecture": "x86_64",
            "agent_version": "1.0.0",
        },
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def agent_headers(
    agent_id: str,
    secret_hex: str,
    method: str,
    path: str,
    body: bytes,
    *,
    timestamp: str | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    """Build valid HMAC signing headers for an agent request."""
    secret = bytes.fromhex(secret_hex)
    ts = timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    nonce = nonce or str(uuid4())
    body_digest = hashlib.sha256(body).hexdigest()
    message = f"{ts}\n{nonce}\n{method}\n{path}\n{body_digest}"
    signature = hmac.new(secret, message.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "X-HG-Agent-Id": agent_id,
        "X-HG-Timestamp": ts,
        "X-HG-Nonce": nonce,
        "X-HG-Signature": signature,
    }


def post_signed_batch(
    client: FlaskClient, agent_id: str, secret_hex: str, body: dict[str, object], **kwargs: object
) -> object:
    import json

    raw = json.dumps(body).encode("utf-8")
    headers = agent_headers(agent_id, secret_hex, "POST", "/api/v1/agent/batches", raw, **kwargs)
    return client.post(
        "/api/v1/agent/batches", data=raw, content_type="application/json", headers=headers
    )


def valid_batch(batch_id: str | None = None, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "batch_id": batch_id or str(uuid4()),
        "collected_at": "2026-07-31T10:00:00Z",
        "metrics": {
            "cpu_percent": 12.5,
            "memory_percent": 43.2,
            "disk_percent": 55.0,
            "network_bytes_sent": 1024,
            "network_bytes_recv": 4096,
        },
        "inventory": {
            "hostname": "agent-01",
            "os": "windows",
            "os_version": "11",
            "architecture": "x86_64",
            "agent_version": "1.0.0",
            "boot_time": "2026-07-31T08:00:00Z",
            "ip_addresses": ["10.0.0.5"],
        },
        "processes": [
            {
                "pid": 1234,
                "name": "svchost.exe",
                "executable": "C:\\Windows\\System32\\svchost.exe",
                "username": "SYSTEM",
                "started_at": "2026-07-31T08:30:00Z",
            }
        ],
        "listening_ports": [
            {"protocol": "tcp", "local_address": "0.0.0.0", "local_port": 443, "pid": 1234}
        ],
        "events": [
            {
                "event_id": str(uuid4()),
                "event_type": "process_creation",
                "occurred_at": "2026-07-31T09:59:00Z",
                "severity": "medium",
                "summary": "Suspicious process spawned",
                "source_ip": "10.0.0.9",
                "username": "bob",
                "metadata": {"parent": "powershell.exe"},
            }
        ],
        "file_changes": [
            {
                "event_id": str(uuid4()),
                "path": "C:\\temp\\evil.exe",
                "change_type": "created",
                "occurred_at": "2026-07-31T09:58:00Z",
                "sha256": "a" * 64,
                "size": 2048,
            }
        ],
        "baseline_results": [
            {
                "check_id": "cis-2.3.1",
                "status": "fail",
                "checked_at": "2026-07-31T09:00:00Z",
                "message": "Guest account is enabled",
            }
        ],
    }
    payload.update(overrides)
    return payload
