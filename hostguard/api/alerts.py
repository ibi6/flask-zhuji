from __future__ import annotations

from typing import Any

from flask import Blueprint, g, jsonify, request

from ..authz import require_auth, require_role, write_audit
from ..errors import ApiError
from ..extensions import db
from ..models import Alert, AlertTransition, utcnow
from ..schemas import AlertTransitionInput, PaginationInput
from . import paginate

bp = Blueprint("alerts", __name__, url_prefix="/api/v1/alerts")


@bp.get("")
@require_auth
def list_alerts() -> tuple[Any, int]:
    params = PaginationInput.model_validate(
        {"page": request.args.get("page", 1), "page_size": request.args.get("page_size", 20)}
    )
    query = Alert.query
    status = request.args.get("status")
    severity = request.args.get("severity")
    host_id = request.args.get("host_id")
    if status:
        query = query.filter(Alert.status == status)
    if severity:
        query = query.filter(Alert.severity == severity)
    if host_id:
        query = query.filter(Alert.host_id == host_id)
    total = query.count()
    items = (
        query.order_by(Alert.last_seen_at.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
        .all()
    )
    return paginate([alert.to_dict() for alert in items], params.page, params.page_size, total)


@bp.get("/<alert_id>")
@require_auth
def get_alert(alert_id: str) -> tuple[Any, int]:
    alert = db.session.get(Alert, alert_id)
    if alert is None:
        raise ApiError("alert_not_found", "The alert was not found.", 404)
    data = alert.to_dict()
    data["transitions"] = [
        transition.to_dict() for transition in sorted(
            alert.transitions, key=lambda item: item.created_at
        )
    ]
    return jsonify({"alert": data}), 200


@bp.post("/<alert_id>/transitions")
@require_role("admin", "analyst")
def transition_alert(alert_id: str) -> tuple[Any, int]:
    payload = AlertTransitionInput.model_validate(request.get_json(silent=True) or {})
    alert = db.session.get(Alert, alert_id)
    if alert is None:
        raise ApiError("alert_not_found", "The alert was not found.", 404)
    if payload.status == alert.status:
        raise ApiError("alert_status_unchanged", "The alert is already in this status.", 409)

    from_status = alert.status
    alert.status = payload.status
    alert.last_seen_at = utcnow()
    if payload.status == "resolved":
        alert.resolved_at = utcnow()
    elif alert.resolved_at is not None:
        alert.resolved_at = None
    db.session.add(
        AlertTransition(
            alert_id=alert.id,
            from_status=from_status,
            to_status=payload.status,
            actor_user_id=g.current_user.id,
            reason=payload.reason,
        )
    )
    write_audit(
        "alert.transition",
        "alert",
        alert.id,
        details={"from_status": from_status, "to_status": payload.status},
    )
    db.session.commit()
    return jsonify({"alert": alert.to_dict()}), 200
