from __future__ import annotations

import functools
from collections.abc import Callable
from datetime import timedelta
from typing import Any, TypeVar

from flask import current_app, g, request
from sqlalchemy import delete

from .errors import ApiError
from .extensions import db
from .models import AuditLog, User, WebSession, utcnow
from .security import SESSION_COOKIE, generate_token, hash_token

F = TypeVar("F", bound=Callable[..., Any])


def _session_ttl() -> timedelta:
    return timedelta(hours=int(current_app.config["SESSION_TTL_HOURS"]))


def create_session(user: User, ip_address: str | None, user_agent: str | None) -> str:
    """Create a server-side session; returns the raw cookie token (hash stored in DB)."""
    token = generate_token()
    db.session.add(
        WebSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=utcnow() + _session_ttl(),
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
    return token


def load_user_from_request() -> User | None:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        return None
    session = WebSession.query.filter_by(token_hash=hash_token(token), revoked_at=None).first()
    if session is None or session.expires_at < utcnow():
        return None
    user = db.session.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    return user

def revoke_current_session() -> None:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        return
    WebSession.query.filter_by(token_hash=hash_token(token), revoked_at=None).update(
        {"revoked_at": utcnow()}
    )


def revoke_all_sessions(user_id: str) -> None:
    WebSession.query.filter_by(user_id=user_id, revoked_at=None).update(
        {"revoked_at": utcnow()}
    )


def purge_expired_sessions() -> None:
    db.session.execute(delete(WebSession).where(WebSession.expires_at < utcnow()))


def require_auth(fn: F) -> F:
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if getattr(g, "current_user", None) is None:
            raise ApiError("authentication_required", "Authentication is required.", 401)
        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def require_role(*roles: str) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        @require_auth
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = g.current_user
            if user.role not in roles:
                raise ApiError(
                    "forbidden",
                    "You do not have permission to perform this action.",
                    403,
                )
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def write_audit(
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    outcome: str = "success",
    details: dict[str, Any] | None = None,
) -> None:
    actor = getattr(g, "current_user", None)
    actor_id = actor.id if actor is not None else None
    db.session.add(
        AuditLog(
            actor_user_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            details=details or {},
            request_id=getattr(g, "request_id", ""),
            ip_address=request.remote_addr,
        )
    )
