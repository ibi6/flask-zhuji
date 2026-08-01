from __future__ import annotations

import smtplib
import urllib.request
from datetime import datetime
from typing import Any

from .extensions import db
from .models import (
    Alert,
    NotificationChannel,
    NotificationDelivery,
    isoformat_utc,
    utcnow,
)

MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 60


def create_deliveries_for_alert(alert_id: str) -> list[NotificationDelivery]:
    """Create one pending delivery per enabled channel for an alert (idempotent)."""
    alert = db.session.get(Alert, alert_id)
    if alert is None:
        return []
    created: list[NotificationDelivery] = []
    for channel in NotificationChannel.query.filter_by(enabled=True).all():
        existing = NotificationDelivery.query.filter_by(
            alert_id=alert_id, channel_id=channel.id
        ).first()
        if existing is not None:
            continue
        delivery = NotificationDelivery(
            alert_id=alert_id,
            channel_id=channel.id,
            status="pending",
            attempts=0,
        )
        db.session.add(delivery)
        created.append(delivery)
    return created


def process_deliveries(now: datetime | None = None) -> list[str]:
    """Deliver pending/retrying notifications; returns processed delivery ids."""
    now = now or utcnow()
    deliveries = (
        NotificationDelivery.query.filter(
            NotificationDelivery.status.in_(["pending", "retrying"])
        )
        .order_by(NotificationDelivery.created_at)
        .all()
    )
    processed: list[str] = []
    for delivery in deliveries:
        if delivery.attempts >= MAX_ATTEMPTS:
            delivery.status = "failed"
            delivery.error = delivery.error or "max attempts reached"
            db.session.add(delivery)
            processed.append(delivery.id)
            continue

        try:
            _send(delivery)
        except Exception as exc:  # noqa: BLE001 - delivery failures are expected
            delivery.attempts += 1
            delivery.error = str(exc)[:1000]
            delivery.status = "failed" if delivery.attempts >= MAX_ATTEMPTS else "retrying"
            db.session.add(delivery)
            processed.append(delivery.id)
            continue

        delivery.attempts += 1
        delivery.status = "sent"
        delivery.sent_at = now
        delivery.error = None
        db.session.add(delivery)
        processed.append(delivery.id)

    if processed:
        db.session.commit()
    return processed


def _send(delivery: NotificationDelivery) -> None:
    """Send one delivery through its channel; raises on failure so retry works."""
    channel = db.session.get(NotificationChannel, delivery.channel_id)
    alert = db.session.get(Alert, delivery.alert_id)
    if channel is None or not channel.enabled:
        raise RuntimeError("notification channel is missing or disabled")
    if alert is None:
        raise RuntimeError("alert is missing")

    if channel.channel_type == "webhook":
        _send_webhook(channel, alert)
    elif channel.channel_type == "email":
        _send_email(channel, alert)
    else:
        raise RuntimeError(f"unsupported channel type: {channel.channel_type}")


def _alert_payload(alert: Alert) -> dict[str, Any]:
    return {
        "alert_id": alert.id,
        "severity": alert.severity,
        "status": alert.status,
        "title": alert.title,
        "description": alert.description,
        "host_id": alert.host_id,
        "first_seen_at": isoformat_utc(alert.first_seen_at),
    }


def _send_webhook(channel: NotificationChannel, alert: Alert) -> None:
    """POST the alert payload to the configured webhook URL."""
    import json

    url = channel.config.get("url")
    if not url:
        raise RuntimeError("webhook channel has no url configured")
    body = json.dumps(_alert_payload(alert)).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - webhook URL is admin-configured
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        if response.status >= 400:
            raise RuntimeError(f"webhook returned HTTP {response.status}")


def _send_email(channel: NotificationChannel, alert: Alert) -> None:
    """Send an alert email via the configured SMTP server (skeleton transport)."""
    config = channel.config
    host = config.get("host")
    recipients = config.get("recipients")
    if not host or not isinstance(recipients, list) or not recipients:
        raise RuntimeError("email channel requires host and a recipients list")
    port = int(config.get("port", 25))
    from_addr = config.get("from", "hostguard@localhost")
    subject = f"[HostGuard] {alert.severity.upper()} alert: {alert.title}"
    message = f"Subject: {subject}\r\n\r\n{alert.description or alert.title}"
    with smtplib.SMTP(host, port, timeout=10) as server:
        username = config.get("username")
        if username:
            server.login(username, config.get("password") or "")
        server.sendmail(from_addr, recipients, message.encode("utf-8"))
