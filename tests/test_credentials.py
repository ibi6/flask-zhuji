from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from hostguard_agent.credentials import (
    AgentCredentials,
    LinuxFileCredentialStore,
    WindowsDpapiCredentialStore,
)


class ReversingProtector:
    def protect(self, value: bytes) -> bytes:
        return value[::-1]

    def unprotect(self, value: bytes) -> bytes:
        return value[::-1]


def test_linux_store_round_trips_and_sets_owner_only_permissions(tmp_path: Path) -> None:
    path = tmp_path / "credentials.json"
    store = LinuxFileCredentialStore(path)
    credentials = AgentCredentials(agent_id="agent-id", secret="sensitive-secret")

    store.save(credentials)

    assert store.load() == credentials
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_windows_store_never_writes_plaintext_secret(tmp_path: Path) -> None:
    path = tmp_path / "credentials.json"
    store = WindowsDpapiCredentialStore(path, protector=ReversingProtector())
    credentials = AgentCredentials(agent_id="agent-id", secret="sensitive-secret")

    store.save(credentials)

    raw = path.read_text(encoding="utf-8")
    assert "sensitive-secret" not in raw
    assert json.loads(raw)["agent_id"] == "agent-id"
    assert store.load() == credentials


def test_invalid_credential_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "credentials.json"
    path.write_text('{"agent_id":"only"}', encoding="utf-8")

    with pytest.raises(ValueError, match="credential"):
        LinuxFileCredentialStore(path).load()
