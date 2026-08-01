from __future__ import annotations

from typing import Any

from flask import Blueprint, g, jsonify, request
from sqlalchemy import or_

from ..authz import require_role, revoke_all_sessions, write_audit
from ..errors import ApiError
from ..extensions import db
from ..models import User
from ..schemas import CreateUserInput, PaginationInput, UpdateUserInput
from . import paginate

bp = Blueprint("users", __name__, url_prefix="/api/v1/users")


def _paginated_user_rows() -> tuple[list[User], int, int, int]:
    params = PaginationInput.model_validate(
        {"page": request.args.get("page", 1), "page_size": request.args.get("page_size", 20)}
    )
    query = User.query
    search = request.args.get("search", "").strip()
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(User.username.ilike(pattern), User.email.ilike(pattern))
        )
    total = query.count()
    items = (
        query.order_by(User.created_at.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
        .all()
    )
    return items, params.page, params.page_size, total


@bp.get("")
@require_role("admin")
def list_users() -> tuple[Any, int]:
    items, page, page_size, total = _paginated_user_rows()
    return paginate([user.to_dict() for user in items], page, page_size, total)


@bp.post("")
@require_role("admin")
def create_user() -> tuple[Any, int]:
    payload = CreateUserInput.model_validate(request.get_json(silent=True) or {})
    normalized_username = payload.username.strip().lower()
    if User.query.filter_by(username=normalized_username).first() is not None:
        raise ApiError("user_already_exists", "A user with this username already exists.", 409)
    if User.query.filter_by(email=str(payload.email).strip().lower()).first() is not None:
        raise ApiError("user_already_exists", "A user with this email already exists.", 409)

    user = User(username=payload.username, email=str(payload.email), role=payload.role)
    user.set_password(payload.password)
    db.session.add(user)
    write_audit("user.create", "user")
    db.session.commit()
    return jsonify({"user": user.to_dict()}), 201


@bp.patch("/<user_id>")
@require_role("admin")
def update_user(user_id: str) -> tuple[Any, int]:
    payload = UpdateUserInput.model_validate(request.get_json(silent=True) or {})
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("user_not_found", "The user was not found.", 404)

    actor = g.current_user
    if actor.id == user.id:
        if payload.is_active is False:
            raise ApiError(
                "self_deactivation_forbidden",
                "You cannot deactivate your own account.",
                409,
            )
        if payload.role is not None and user.role == "admin" and payload.role != "admin":
            raise ApiError("self_demotion_forbidden", "You cannot remove your own admin role.", 409)

    if payload.email is not None:
        email = str(payload.email)
        duplicate = User.query.filter(User.email == email, User.id != user.id).first()
        if duplicate is not None:
            raise ApiError("user_already_exists", "A user with this email already exists.", 409)
        user.email = email
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
        if not user.is_active:
            revoke_all_sessions(user.id)

    write_audit("user.update", "user", user.id)
    db.session.commit()
    return jsonify({"user": user.to_dict()}), 200


@bp.delete("/<user_id>")
@require_role("admin")
def delete_user(user_id: str) -> tuple[Any, int]:
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("user_not_found", "The user was not found.", 404)
    if user.id == g.current_user.id:
        raise ApiError("self_deletion_forbidden", "You cannot delete your own account.", 409)

    user.is_active = False
    revoke_all_sessions(user.id)
    write_audit("user.delete", "user", user.id)
    db.session.commit()
    return jsonify({}), 204
