"""Secret-at-rest protection abstraction.

The :class:`SecretStore` protocol transforms a plaintext secret into an
opaque blob that is safe to persist. Concrete implementations:

* :class:`DpapiSecretStore` -- Windows DPAPI (``CryptProtectData`` /
  ``CryptUnprotectData``) via ``ctypes`` against the standard Win32 API.
* :class:`MemorySecretStore` -- identity transform, intended for tests and
  for stores that rely on file permissions (Linux ``0600``) instead.
* :class:`LinuxFileSecretStore` -- protects by writing an owner-only file
  (``0600``); transform is identity because permission bits are the
  protection mechanism.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import os
import stat
from pathlib import Path
from typing import Protocol, runtime_checkable

__all__ = [
    "SecretStore",
    "DpapiSecretStore",
    "LinuxFileSecretStore",
    "MemorySecretStore",
    "default_secret_store",
]


@runtime_checkable
class SecretStore(Protocol):
    """Transforms plaintext secrets to/from an at-rest protected form."""

    def protect(self, plaintext: bytes) -> bytes:
        """Return the protected form of ``plaintext``."""
        ...

    def unprotect(self, protected: bytes) -> bytes:
        """Return the plaintext for ``protected``."""
        ...


class MemorySecretStore:
    """Identity store for tests and permission-based protection."""

    def protect(self, plaintext: bytes) -> bytes:
        return plaintext

    def unprotect(self, protected: bytes) -> bytes:
        return protected


class DpapiSecretStore:
    """Windows DPAPI protection backed by ``crypt32.dll``.

    Uses the documented Win32 API surface only; no private Windows
    internals. ``CRYPTPROTECT_UI_FORBIDDEN`` prevents interactive prompts.
    """

    _CRYPTPROTECT_UI_FORBIDDEN = 0x1

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows DPAPI is only available on Windows")
        self._crypt32 = ctypes.windll.crypt32
        self._kernel32 = ctypes.windll.kernel32
        self._local_free = self._kernel32.LocalFree
        self._local_free.argtypes = [wintypes.HLOCAL]
        self._local_free.restype = wintypes.HLOCAL
        self._crypt_protect = self._crypt32.CryptProtectData
        self._crypt_unprotect = self._crypt32.CryptUnprotectData

    def protect(self, plaintext: bytes) -> bytes:
        data_in = self._blob_from_bytes(plaintext)
        data_out = self._DATA_BLOB()
        ok = self._crypt_protect(
            ctypes.byref(data_in),
            None,
            None,
            None,
            None,
            self._CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(data_out),
        )
        if not ok:
            raise OSError(self._win32_error("CryptProtectData failed"))
        try:
            return self._blob_to_bytes(data_out)
        finally:
            self._free_blob(data_out)

    def unprotect(self, protected: bytes) -> bytes:
        data_in = self._blob_from_bytes(protected)
        data_out = self._DATA_BLOB()
        ok = self._crypt_unprotect(
            ctypes.byref(data_in),
            None,
            None,
            None,
            None,
            self._CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(data_out),
        )
        if not ok:
            raise OSError(self._win32_error("CryptUnprotectData failed"))
        try:
            return self._blob_to_bytes(data_out)
        finally:
            self._free_blob(data_out)

    def _blob_from_bytes(self, value: bytes) -> _DATA_BLOB:
        buffer = ctypes.create_string_buffer(value, len(value))
        blob = self._DATA_BLOB()
        blob.cbData = len(value)
        blob.pbData = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))
        return blob

    @staticmethod
    def _blob_to_bytes(blob: _DATA_BLOB) -> bytes:
        size = int(blob.cbData)
        if size == 0:
            return b""
        return ctypes.string_at(blob.pbData, size)

    def _free_blob(self, blob: _DATA_BLOB) -> None:
        if blob.pbData:
            self._local_free(blob.pbData)
            blob.pbData = None

    def _win32_error(self, prefix: str) -> str:
        code = self._kernel32.GetLastError()
        return f"{prefix} (Windows error {code})"


class LinuxFileSecretStore:
    """Protection via an owner-only file on POSIX systems.

    The transform is identity; confidentiality comes from ``0600`` file
    permissions. On non-POSIX platforms the file is still written, which
    keeps it usable as a plain fallback store.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def protect(self, plaintext: bytes) -> bytes:
        self._write_owner_only(plaintext)
        return plaintext

    def unprotect(self, protected: bytes) -> bytes:
        return protected

    def _write_owner_only(self, content: bytes) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix(self._path.suffix + ".tmp")
        fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, content)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(temp, 0o600)
        os.replace(temp, self._path)


def default_secret_store(path: Path | None = None) -> SecretStore:
    """Return the platform-appropriate secret store.

    DPAPI on Windows; otherwise an owner-only file (``0600``) on POSIX and
    an in-memory identity store elsewhere.
    """
    if os.name == "nt":
        return DpapiSecretStore()
    if os.name == "posix" and path is not None:
        return LinuxFileSecretStore(path)
    return MemorySecretStore()


def assert_owner_only(path: Path) -> None:
    """Raise if ``path`` exists with non-owner-only permissions on POSIX."""
    if os.name == "posix" and path.exists():
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise OSError(f"permissions on {path} are too permissive: {mode:o}")
