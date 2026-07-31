from __future__ import annotations

from uuid import uuid4

from flask import Flask
from flask.testing import FlaskClient

from hostguard.extensions import db
from hostguard.models import (
    Alert,
    Host,
    InventorySnapshot,
    MetricSample,
    SecurityEvent,
    User,
)

from .conftest import login


def _create_host(app: Flask, hostname: str, status: str = "online") -> Host:
    with app.app_context():
        host = Host(hostname=hostname, os="linux", source="real", status=status)
        db.session.add(host)
        db.session.commit()
        db.session.refresh(host)
        db.session.expunge(host)
        return host


def _login_admin(client: FlaskClient, app: Flask) -> None:
    with app.app_context():
        admin = User(username="boss", email="boss@example.com", role="admin")
        admin.set_password("Boss-Password-42")
        db.session.add(admin)
        db.session.commit()
    login(client, "boss", "Boss-Password-42")


def test_host_detail_returns_404_for_missing_host(
    client: FlaskClient, app: Flask
) -> None:
    _login_admin(client, app)
    response = client.get("/api/v1/hosts/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "host_not_found"


def test_host_detail_includes_latest_metric_and_inventory(
    client: FlaskClient, app: Flask
) -> None:
    _login_admin(client, app)
    host = _create_host(app, "web-01")
    with app.app_context():
        db.session.add(
            MetricSample(
                host_id=host.id,
                batch_id=str(uuid4()),
                collected_at=db.func.now(),
                cpu_percent=7.5,
                memory_percent=30.0,
                disk_percent=60.0,
                network_bytes_sent=1,
                network_bytes_recv=2,
            )
        )
        db.session.add(
            InventorySnapshot(
                host_id=host.id,
                batch_id=str(uuid4()),
                hostname="web-01",
                os="linux",
                os_version="ubuntu-24.04",
                architecture="x86_64",
                agent_version="1.0.0",
                ip_addresses=["10.1.1.1"],
            )
        )
        db.session.commit()

    response = client.get(f"/api/v1/hosts/{host.id}")
    assert response.status_code == 200
    body = response.get_json()["host"]
    assert body["hostname"] == "web-01"
    assert body["last_metric"]["cpu_percent"] == 7.5
    assert body["inventory"]["architecture"] == "x86_64"


def test_host_list_filters_by_status(client: FlaskClient, app: Flask) -> None:
    _login_admin(client, app)
    _create_host(app, "online-01", "online")
    _create_host(app, "offline-01", "offline")

    response = client.get("/api/v1/hosts?status=online")
    body = response.get_json()
    assert body["total"] == 1
    assert body["items"][0]["hostname"] == "online-01"


def test_dashboard_summary_counts_real_rows(client: FlaskClient, app: Flask) -> None:
    _login_admin(client, app)
    _create_host(app, "h1", "online")
    _create_host(app, "h2", "offline")
    event_host = _create_host(app, "h3", "online")
    with app.app_context():
        db.session.add(Alert(title="a1", severity="high", status="open", description=None))
        db.session.add(
            Alert(title="a2", severity="critical", status="open", description=None)
        )
        db.session.add(
            SecurityEvent(
                id=str(uuid4()),
                host_id=event_host.id,
                batch_id=str(uuid4()),
                event_type="process_creation",
                occurred_at=db.func.now(),
                severity="medium",
                summary="x",
            )
        )
        db.session.commit()

    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    summary = response.get_json()["summary"]
    assert summary["hosts"]["total"] == 3
    assert summary["hosts"]["by_status"]["online"] == 2
    assert summary["alerts"]["total"] == 2
    assert summary["alerts"]["by_severity"]["critical"] == 1
    assert len(summary["recent_events"]) == 1
