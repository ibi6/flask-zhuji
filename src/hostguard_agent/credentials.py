"""Agent credential persistence.

Credentials are ``(agent_id, secret)`` pairs returned by the enrollment
endpoint exactly once. Stores persist them at rest:

* :class:`LinuxFileCredentialStore` -- JSON file with ``0600`` permissions
  (POSIX). On Windows the same layout is used for cross-platform tests.
* :class:`WindowsDpapiCredentialStore` -- the secret is protected with
  DPAPI before writing; the agent id remains plaintext for discovery.
* :class:`MemoryCredentialStore` -- in-memory, for tests.

The on-disk format is a JSON object::

    {"version": 1, "protection": "none" | "dpapi",
     "agent_id": "...", "secret": "<base64>"}
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .secrets import DpapiSecretStore, MemorySecretStore, SecretStore, assert_owner_only

__all__ = [
    "AgentCredentials",
    "CredentialStore",
    "LinuxFileCredentialStore",
    "WindowsDpapiCredentialStore",
    "MemoryCredentialStore",
]

_FORMAT_VERSION = 1


@dataclass(frozen=True)
class AgentCredentials:
    """Agent identity material issued once at enrollment."""

    agent_id: str
    secret: str

    def __post_init__(self) -> None:
        if not self.agent_id:
            raise ValueError("agent_id must not be empty")
        if not self.secret:
            raise ValueError("secret must not be empty")


class CredentialStore(Protocol):
    """Persistence for :class:`AgentCredentials`."""

    def save(self, credentials: AgentCredentials) -> None: ...

    def load(self) -> AgentCredentials: ...


class _JsonFileStore:
    """Shared JSON file read/write with atomic owner-only writes."""

    def __init__(self, path: Path, *, protection: str, store: SecretStore) -> None:
        self._path = path
        self._protection = protection
        self._store = store

    def save(self, credentials: AgentCredentials) -> None:
        protected = self._store.protect(credentials.secret.encode("utf-8"))
        payload = {
            "version": _FORMAT_VERSION,
            "protection": self._protection,
            "agent_id": credentials.agent_id,
            "secret": base64.b64encode(protected).decode("ascii"),
        }
        self._write(json.dumps(payload, sort_keys=True).encode("utf-8"))

    def load(self) -> AgentCredentials:
        if not self._path.exists():
            raise FileNotFoundError(f"no credentials file at {self._path}")
        assert_owner_only(self._path)
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            raise ValueError(f"invalid credential file {self._path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"invalid credential file {self._path}: expected an object")
        if payload.get("version") != _FORMAT_VERSION:
            raise ValueError(f"invalid credential file {self._path}: unsupported version")
        if payload.get("protection") != self._protection:
            raise ValueError(f"invalid credential file {self._path}: unexpected protection scheme")
        agent_id = payload.get("agent_id")
        secret_b64 = payload.get("secret")
        if not isinstance(agent_id, str) or not agent_id:
            raise ValueError(f"invalid credential file {self._path}: missing agent_id")
        if not isinstance(secret_b64, str) or not secret_b64:
            raise ValueError(f"invalid credential file {self._path}: missing secret")
        try:
            protected = base64.b64decode(secret_b64.encode("ascii"), validate=True)
        except ValueError as exc:
            raise ValueError(f"invalid credential file {self._path}: malformed secret") from exc
        secret = self._store.unprotect(protected).decode("utf-8")
        return AgentCredentials(agent_id=agent_id, secret=secret)

    def _write(self, content: bytes) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix(self._path.suffix + ".tmp")
        fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, content)
            os.fsync(fd)
        finally:
            os.close(fd)
        if os.name == "posix":
            os.chmod(temp, 0o600)
        os.replace(temp, self._path)


class LinuxFileCredentialStore(_JsonFileStore):
    """File-backed store whose protection is ``0600`` permissions.

    The secret is written base64-encoded; confidentiality relies on the
    file being owner-only.
    """

    def __init__(self, path: Path) -> None:
        super().__init__(path, protection="none", store=MemorySecretStore())


class WindowsDpapiCredentialStore(_JsonFileStore):
    """File-backed store protecting the secret with DPAPI.

    ``protector`` is injected for tests; when omitted a real DPAPI store
    (``ctypes`` against ``crypt32.dll``) is used.
    """

    def __init__(self, path: Path, protector: SecretStore | None = None) -> None:
        super().__init__(path, protection="dpapi", store=protector or DpapiSecretStore())


class MemoryCredentialStore(CredentialStore):
    """In-memory store for tests and simulated agents."""

    def __init__(self) -> None:
        self._credentials: AgentCredentials | None = None

    def save(self, credentials: AgentCredentials) -> None:
        self._credentials = credentials

    def load(self) -> AgentCredentials:
        if self._credentials is None:
            raise FileNotFoundError("no credentials stored")
        return self._credentials
