from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify
from sqlalchemy import func

from ..authz import require_auth
from ..extensions import db
from ..models import Alert, Host, SecurityEvent

bp = Blueprint("dashboard", __name__, url_prefix="/api/v1/dashboard")


def _severity_breakdown() -> dict[str, int]:
    rows = (
        db.session.query(Alert.severity, func.count(Alert.id))
        .group_by(Alert.severity)
        .all()
    )
    return {severity: int(count) for severity, count in rows}


@bp.get("/summary")
@require_auth
def get_dashboard_summary() -> tuple[Any, int]:
    hosts_by_status = {
        status: int(count)
        for status, count in (
            db.session.query(Host.status, func.count(Host.id)).group_by(Host.status).all()
        )
    }
    alerts_by_status = {
        status: int(count)
        for status, count in (
            db.session.query(Alert.status, func.count(Alert.id)).group_by(Alert.status).all()
        )
    }
    recent_events = (
        SecurityEvent.query.order_by(SecurityEvent.occurred_at.desc()).limit(10).all()
    )
    summary = {
        "hosts": {
            "total": sum(hosts_by_status.values()),
            "by_status": hosts_by_status,
        },
        "alerts": {
            "total": sum(alerts_by_status.values()),
            "by_status": alerts_by_status,
            "by_severity": _severity_breakdown(),
        },
        "recent_events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "severity": event.severity,
                "summary": event.summary,
                "occurred_at": event.occurred_at.isoformat().replace("+00:00", "Z"),
            }
            for event in recent_events
        ],
    }
    return jsonify({"summary": summary}), 200
