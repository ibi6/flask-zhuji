from __future__ import annotations

import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parents[1]
    SECRET_KEY = os.getenv("HOSTGUARD_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'instance' / 'hostguard.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SESSION_COOKIE_NAME = "hostguard_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Strict"
    SESSION_COOKIE_SECURE = os.getenv("HOSTGUARD_COOKIE_SECURE", "true").lower() == "true"
    SESSION_TTL_HOURS = int(os.getenv("HOSTGUARD_SESSION_TTL_HOURS", "12"))
    CSRF_TTL_SECONDS = int(os.getenv("HOSTGUARD_CSRF_TTL_SECONDS", "3600"))
    LOGIN_RATE_LIMIT = os.getenv("HOSTGUARD_LOGIN_RATE_LIMIT", "5 per minute")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    MAX_CONTENT_LENGTH = 1024 * 1024
    JSON_SORT_KEYS = False
    REPORT_STORAGE_DIR = str(BASE_DIR / "instance" / "reports")


def validate_config(config: dict[str, object]) -> None:
    secret = config.get("SECRET_KEY")
    if not isinstance(secret, str) or len(secret) < 32:
        raise RuntimeError("HOSTGUARD_SECRET_KEY must contain at least 32 characters")

    ttl = config.get("SESSION_TTL_HOURS")
    if not isinstance(ttl, int) or ttl < 1 or ttl > 168:
        raise RuntimeError("SESSION_TTL_HOURS must be between 1 and 168")

