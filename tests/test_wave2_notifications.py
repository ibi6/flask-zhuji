from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient

from hostguard.extensions import db
from hostguard.models import (
    Alert,
    DetectionRule,
    NotificationChannel,
    NotificationDelivery,
    User,
)
from hostguard.notifications import process_deliveries

from .conftest import (
    create_enrollment_token,
    csrf_token,
    enroll_agent,
    login,
    post_signed_batch,
    valid_batch,
)


def _channel(app: Flask, channel_type: str = "webhook") -> str:
    with app.app_context():
        config = {"url": "https://example.com/hook"} if channel_type == "webhook" else {
            "host": "smtp.example.com",
            "recipients": ["sec@example.com"],
        }
        channel = NotificationChannel(
            name=f"ch-{channel_type}",
            channel_type=channel_type,
            config=config,
            enabled=True,
        )
        db.session.add(channel)
        db.session.commit()
        return channel.id


def _delivery(app: Flask, channel_id: str) -> str:
    with app.app_context():
        alert = Alert(title="t", severity="high", status="open", description="desc")
        db.session.add(alert)
        db.session.flush()
        delivery = NotificationDelivery(
            alert_id=alert.id, channel_id=channel_id, status="pending", attempts=0
        )
        db.session.add(delivery)
        db.session.commit()
        return delivery.id


def test_webhook_delivery_is_sent(monkeypatch, app: Flask) -> None:
    sent: list[tuple[str, str]] = []

    def fake_send_webhook(channel: NotificationChannel, alert: Alert) -> None:
        sent.append((channel.config.get("url"), alert.title))

    monkeypatch.setattr("hostguard.notifications._send_webhook", fake_send_webhook)
    channel_id = _channel(app)
    delivery_id = _delivery(app, channel_id)

    with app.app_context():
        processed = process_deliveries()
        assert delivery_id in processed
        delivery = db.session.get(NotificationDelivery, delivery_id)
        assert delivery.status == "sent"
        assert delivery.attempts == 1
        assert delivery.sent_at is not None
        assert delivery.error is None

    assert sent == [("https://example.com/hook", "t")]


def test_email_delivery_is_sent(monkeypatch, app: Flask) -> None:
    sent: list[str] = []

    def fake_send_email(channel: NotificationChannel, alert: Alert) -> None:
        sent.append(channel.config.get("host"))

    monkeypatch.setattr("hostguard.notifications._send_email", fake_send_email)
    channel_id = _channel(app, channel_type="email")
    delivery_id = _delivery(app, channel_id)

    with app.app_context():
        process_deliveries()
        delivery = db.session.get(NotificationDelivery, delivery_id)
        assert delivery.status == "sent"

    assert sent == ["smtp.example.com"]


def test_failed_delivery_retries_then_fails(monkeypatch, app: Flask) -> None:
    def boom(*_args: object) -> None:
        raise RuntimeError("network down")

    monkeypatch.setattr("hostguard.notifications._send", boom)
    channel_id = _channel(app)
    delivery_id = _delivery(app, channel_id)

    with app.app_context():
        process_deliveries()
        delivery = db.session.get(NotificationDelivery, delivery_id)
        assert delivery.status == "retrying"
        assert delivery.attempts == 1

        process_deliveries()
        delivery = db.session.get(NotificationDelivery, delivery_id)
        assert delivery.status == "retrying"
        assert delivery.attempts == 2

        process_deliveries()
        delivery = db.session.get(NotificationDelivery, delivery_id)
        assert delivery.status == "failed"
        assert delivery.attempts == 3
        assert "network down" in delivery.error


def test_alert_generation_creates_pending_delivery(
    client: FlaskClient, app: Flask
) -> None:
    channel_id = _channel(app)
    with app.app_context():
        rule = DetectionRule(
            name="high-cpu",
            rule_type="cpu_usage",
            enabled=True,
            severity="high",
            criteria={"threshold": 10},
        )
        db.session.add(rule)
        db.session.commit()
        rule_id = rule.id

    token = create_enrollment_token(app)
    agent = enroll_agent(client, token)
    assert post_signed_batch(
        client, agent["agent_id"], agent["agent_secret"], valid_batch()
    ).status_code == 202

    with app.app_context():
        alert = Alert.query.filter_by(rule_id=rule_id).one()
        delivery = NotificationDelivery.query.filter_by(
            alert_id=alert.id, channel_id=channel_id
        ).one()
        assert delivery.status == "pending"
        assert delivery.attempts == 0


def test_create_channel_api_validates_config(client: FlaskClient, app: Flask) -> None:
    with app.app_context():
        admin = User(username="chanadmin", email="chanadmin@example.com", role="admin")
        admin.set_password("Chan-Admin-Password-42")
        db.session.add(admin)
        db.session.commit()

    login(client, "chanadmin", "Chan-Admin-Password-42")

    response = client.post(
        "/api/v1/notifications/channels",
        json={"name": "web", "channel_type": "webhook", "config": {}},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 422

    response = client.post(
        "/api/v1/notifications/channels",
        json={
            "name": "web",
            "channel_type": "webhook",
            "config": {"url": "https://example.com/hook"},
        },
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 201
    assert response.get_json()["channel"]["channel_type"] == "webhook"

    listing = client.get("/api/v1/notifications/channels")
    assert listing.status_code == 200
    assert len(listing.get_json()["items"]) == 1
