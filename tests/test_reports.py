from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient

from hostguard.extensions import db
from hostguard.models import BackgroundJob, ReportJob, User

from .conftest import csrf_token, login


def _login_analyst(client: FlaskClient, app: Flask) -> None:
    with app.app_context():
        analyst = User(username="analyst", email="analyst@example.com", role="analyst")
        analyst.set_password("Analyst-Password-42")
        db.session.add(analyst)
        db.session.commit()
    login(client, "analyst", "Analyst-Password-42")


def test_report_creation_creates_background_and_report_jobs(
    client: FlaskClient, app: Flask
) -> None:
    _login_analyst(client, app)

    response = client.post(
        "/api/v1/reports",
        json={"report_type": "daily_summary", "parameters": {"scope": "all"}},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 202
    body = response.get_json()
    assert body["status"] == "pending"
    assert body["report_id"]
    assert body["job_id"]

    with app.app_context():
        assert BackgroundJob.query.filter_by(id=body["job_id"]).count() == 1
        report = ReportJob.query.filter_by(id=body["report_id"]).one()
        assert report.job_id == body["job_id"]
        assert report.report_type == "daily_summary"


def test_report_creation_validates_type(client: FlaskClient, app: Flask) -> None:
    _login_analyst(client, app)
    response = client.post(
        "/api/v1/reports",
        json={"report_type": ""},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"
