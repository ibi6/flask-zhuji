from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from ..authz import require_auth
from ..extensions import db
from ..models import AuditLog
from ..schemas import PaginationInput
from . import paginate

bp = Blueprint("audit", __name__, url_prefix="/api/v1/audit")


def _audit_to_dict(entry: AuditLog) -> dict[str, Any]:
    return {
        "id": entry.id,
        "actor_user_id": entry.actor_user_id,
        "actor_username": entry.actor.username if entry.actor is not None else None,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "outcome": entry.outcome,
        "details": entry.details,
        "request_id": entry.request_id,
        "ip_address": entry.ip_address,
        "created_at": entry.created_at.isoformat().replace("+00:00", "Z"),
    }


@bp.get("")
@require_auth
def list_audit_entries() -> tuple[Any, int]:
    params = PaginationInput.model_validate(
        {"page": request.args.get("page", 1), "page_size": request.args.get("page_size", 20)}
    )
    query = AuditLog.query
    action = request.args.get("action")
    if action:
        query = query.filter(AuditLog.action == action)
    total = query.count()
    items = (
        query.order_by(AuditLog.created_at.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
        .all()
    )
    return paginate(
        [_audit_to_dict(entry) for entry in items], params.page, params.page_size, total
    )
