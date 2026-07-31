from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, g, jsonify, make_response, request

from ..authz import create_session, require_auth, revoke_current_session, write_audit
from ..errors import ApiError
from ..extensions import db, limiter
from ..models import User, utcnow
from ..schemas import LoginInput
from ..security import CSRF_COOKIE, SESSION_COOKIE, issue_csrf_token

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@bp.get("/csrf")
def get_csrf_token() -> tuple[Any, int]:
    token, max_age = issue_csrf_token()
    response = jsonify({"csrf_token": token})
    response.set_cookie(
        CSRF_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        samesite="Strict",
        secure=current_app.config["SESSION_COOKIE_SECURE"],
        path="/",
    )
    return response, 200


def _login_username_key() -> str:
    payload = request.get_json(silent=True)
    username = payload.get("username") if isinstance(payload, dict) else None
    return str(username or "anonymous")


@bp.post("/login")
@limiter.limit("20 per hour", key_func=_login_username_key)
@limiter.limit(lambda: current_app.config["LOGIN_RATE_LIMIT"])
def login() -> tuple[Any, int]:
    payload = LoginInput.model_validate(request.get_json(silent=True) or {})
    user = User.query.filter_by(username=payload.username).first()
    if user is None or not user.is_active or not user.verify_password(payload.password):
        raise ApiError("invalid_credentials", "Invalid username or password.", 401)

    user_agent = request.user_agent.string[:512]
    token = create_session(user, request.remote_addr, user_agent or None)
    user.last_login_at = utcnow()
    g.current_user = user
    write_audit("auth.login", "user", user.id)
    db.session.commit()

    ttl_seconds = int(current_app.config["SESSION_TTL_HOURS"]) * 3600
    response = jsonify({"user": user.to_dict()})
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=ttl_seconds,
        httponly=True,
        samesite="Strict",
        secure=current_app.config["SESSION_COOKIE_SECURE"],
        path="/",
    )
    return response, 200


@bp.post("/logout")
@require_auth
def logout() -> tuple[Any, int]:
    revoke_current_session()
    write_audit("auth.logout", "user", g.current_user.id)
    db.session.commit()

    response = make_response("", 204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response, 204


@bp.get("/me")
@require_auth
def get_current_user() -> tuple[Any, int]:
    return jsonify({"user": g.current_user.to_dict()}), 200
