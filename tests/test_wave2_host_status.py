from __future__ import annotations

from datetime import timedelta

from flask import Flask
from flask.testing import FlaskClient

from hostguard.extensions import db
from hostguard.host_status import refresh_host_statuses
from hostguard.models import Alert, Host, User, utcnow

from .conftest import login


def test_host_status_is_inferred_from_last_seen(app: Flask) -> None:
    now = utcnow()
    with app.app_context():
        online = Host(
            hostname="o", os="linux", source="real", status="offline",
            last_seen_at=now - timedelta(seconds=60),
        )
        degraded = Host(
            hostname="d", os="linux", source="real", status="offline",
            last_seen_at=now - timedelta(minutes=10),
        )
        stale = Host(
            hostname="f", os="linux", source="real", status="online",
            last_seen_at=now - timedelta(hours=2),
        )
        never = Host(hostname="n", os="linux", source="real", status="online")
        db.session.add_all([online, degraded, stale, never])
        db.session.commit()
        ids = (online.id, degraded.id, stale.id, never.id)

    changed = refresh_host_statuses(now=now)
    assert changed == 3  # the never-reported host keeps its stored status

    with app.app_context():
        assert db.session.get(Host, ids[0]).status == "online"
        assert db.session.get(Host, ids[1]).status == "degraded"
        assert db.session.get(Host, ids[2]).status == "offline"
        assert db.session.get(Host, ids[3]).status == "online"


def test_host_list_reflects_inferred_status(client: FlaskClient, app: Flask) -> None:
    with app.app_context():
        admin = User(username="stathost", email="stathost@example.com", role="admin")
        admin.set_password("Stat-Host-Password-42")
        db.session.add(admin)
        db.session.commit()
        stale = Host(
            hostname="stale", os="linux", source="real", status="online",
            last_seen_at=utcnow() - timedelta(hours=1),
        )
        db.session.add(stale)
        db.session.commit()
    login(client, "stathost", "Stat-Host-Password-42")

    response = client.get("/api/v1/hosts")
    assert response.status_code == 200
    items = response.get_json()["items"]
    assert items[0]["hostname"] == "stale"
    assert items[0]["status"] == "offline"


def test_dashboard_summary_uses_inferred_status_and_risk_trend(
    client: FlaskClient, app: Flask
) -> None:
    with app.app_context():
        admin = User(username="dashadmin", email="dashadmin@example.com", role="admin")
        admin.set_password("Dash-Admin-Password-42")
        db.session.add(admin)
        db.session.commit()
        stale = Host(
            hostname="stale", os="linux", source="real", status="online",
            last_seen_at=utcnow() - timedelta(hours=1),
        )
        live = Host(
            hostname="live", os="linux", source="real", status="offline",
            last_seen_at=utcnow() - timedelta(seconds=10),
        )
        alert = Alert(title="x", severity="high", status="open", description=None)
        db.session.add_all([stale, live, alert])
        db.session.commit()
    login(client, "dashadmin", "Dash-Admin-Password-42")

    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    summary = response.get_json()["summary"]
    assert summary["hosts"]["total"] == 2
    assert summary["hosts"]["by_status"]["online"] == 1
    assert summary["hosts"]["by_status"]["offline"] == 1
    assert summary["alerts"]["total"] == 1
    assert summary["alerts"]["by_severity"]["high"] == 1

    trend = summary["risk_trend"]
    assert len(trend) == 7
    today = utcnow().date().isoformat()
    assert any(item["date"] == today and item["count"] >= 1 for item in trend)
    assert len(summary["recent_events"]) == 0
