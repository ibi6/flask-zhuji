from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from ..authz import require_auth, require_role, write_audit
from ..errors import ApiError
from ..extensions import db
from ..models import NotificationChannel, NotificationDelivery
from ..schemas import NotificationChannelCreateInput, PaginationInput
from . import paginate

bp = Blueprint("notifications", __name__, url_prefix="/api/v1/notifications")


@bp.get("/channels")
@require_auth
def list_channels() -> tuple[Any, int]:
    items = NotificationChannel.query.order_by(NotificationChannel.name).all()
    return jsonify({"items": [channel.to_dict() for channel in items]}), 200


@bp.post("/channels")
@require_role("admin")
def create_channel() -> tuple[Any, int]:
    payload = NotificationChannelCreateInput.model_validate(
        request.get_json(silent=True) or {}
    )
    existing = NotificationChannel.query.filter_by(name=payload.name).first()
    if existing is not None:
        raise ApiError(
            "channel_name_exists", "A channel with this name already exists.", 409
        )
    channel = NotificationChannel(
        name=payload.name,
        channel_type=payload.channel_type,
        config=payload.config,
        enabled=payload.enabled,
    )
    db.session.add(channel)
    write_audit("notification.channel.create", "notification_channel", channel.id)
    db.session.commit()
    return jsonify({"channel": channel.to_dict()}), 201


@bp.get("/deliveries")
@require_auth
def list_deliveries() -> tuple[Any, int]:
    params = PaginationInput.model_validate(
        {"page": request.args.get("page", 1), "page_size": request.args.get("page_size", 20)}
    )
    query = NotificationDelivery.query
    status = request.args.get("status")
    if status:
        query = query.filter(NotificationDelivery.status == status)
    total = query.count()
    items = (
        query.order_by(NotificationDelivery.created_at.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
        .all()
    )
    return paginate(
        [delivery.to_dict() for delivery in items], params.page, params.page_size, total
    )
