from __future__ import annotations

from datetime import timedelta
from typing import Any

from flask import Blueprint, jsonify
from sqlalchemy import func

from ..authz import require_auth
from ..extensions import db
from ..host_status import refresh_host_statuses
from ..models import Alert, Host, SecurityEvent, isoformat_utc, utcnow

bp = Blueprint("dashboard", __name__, url_prefix="/api/v1/dashboard")

RISK_TREND_DAYS = 7


def _severity_breakdown() -> dict[str, int]:
    rows = (
        db.session.query(Alert.severity, func.count(Alert.id))
        .group_by(Alert.severity)
        .all()
    )
    return {severity: int(count) for severity, count in rows}


def _risk_trend(days: int = RISK_TREND_DAYS) -> list[dict[str, Any]]:
    """Alerts created per day over the trailing window (for risk trending)."""
    start = (utcnow() - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    rows = (
        db.session.query(func.date(Alert.first_seen_at), func.count(Alert.id))
        .filter(Alert.first_seen_at >= start)
        .group_by(func.date(Alert.first_seen_at))
        .all()
    )
    counts = {str(day): int(count) for day, count in rows}
    trend = []
    for offset in range(days):
        day = (start + timedelta(days=offset)).date().isoformat()
        trend.append({"date": day, "count": counts.get(day, 0)})
    return trend


@bp.get("/summary")
@require_auth
def get_dashboard_summary() -> tuple[Any, int]:
    refresh_host_statuses()
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
                "occurred_at": isoformat_utc(event.occurred_at),
            }
            for event in recent_events
        ],
        "risk_trend": _risk_trend(),
    }
    return jsonify({"summary": summary}), 200
