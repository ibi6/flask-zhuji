from __future__ import annotations

import json
from pathlib import Path

from flask import Flask
from flask.testing import FlaskClient

from hostguard.extensions import db
from hostguard.models import BackgroundJob, ReportJob, User
from hostguard.reporting import execute_report

from .conftest import csrf_token, login


def _login_analyst(client: FlaskClient, app: Flask) -> None:
    with app.app_context():
        analyst = User(username="analyst2", email="analyst2@example.com", role="analyst")
        analyst.set_password("Analyst-Password-42")
        db.session.add(analyst)
        db.session.commit()
    login(client, "analyst2", "Analyst-Password-42")


def _create_report_job(app: Flask, report_type: str, parameters: dict[str, object]) -> str:
    with app.app_context():
        job = BackgroundJob(
            job_type="report",
            status="pending",
            payload={"report_type": report_type, "parameters": parameters},
        )
        db.session.add(job)
        db.session.flush()
        report = ReportJob(
            job_id=job.id,
            report_type=report_type,
            parameters=parameters,
            status="pending",
        )
        db.session.add(report)
        db.session.commit()
        return job.id


def test_report_job_completes_and_writes_json(app: Flask, tmp_path: Path) -> None:
    app.config["REPORT_STORAGE_DIR"] = str(tmp_path / "reports")
    job_id = _create_report_job(
        app, "daily_summary", {"scope": "all", "format": "json"}
    )

    with app.app_context():
        report = execute_report(job_id)
        assert report is not None
        assert report.status == "completed"
        assert report.file_path is not None
        assert report.expires_at is not None
        file_path = Path(report.file_path)
        assert file_path.exists()
        content = json.loads(file_path.read_text(encoding="utf-8"))
        assert "hosts" in content
        assert "alerts" in content
        assert "risk_trend" in content

        job = db.session.get(BackgroundJob, job_id)
        assert job.status == "completed"
        assert job.finished_at is not None
        assert job.started_at is not None


def test_report_csv_format_writes_csv(app: Flask, tmp_path: Path) -> None:
    app.config["REPORT_STORAGE_DIR"] = str(tmp_path / "reports")
    job_id = _create_report_job(
        app, "daily_summary", {"scope": "all", "format": "csv"}
    )

    with app.app_context():
        report = execute_report(job_id)
        assert report is not None
        assert report.status == "completed"
        file_path = Path(report.file_path)
        assert file_path.suffix == ".csv"
        text = file_path.read_text(encoding="utf-8")
        assert "," in text


def test_unknown_report_type_fails_job(app: Flask, tmp_path: Path) -> None:
    app.config["REPORT_STORAGE_DIR"] = str(tmp_path / "reports")
    job_id = _create_report_job(app, "not_a_real_report", {})

    with app.app_context():
        report = execute_report(job_id)
        assert report is not None
        assert report.status == "failed"
        job = db.session.get(BackgroundJob, job_id)
        assert job.status == "failed"
        assert job.error is not None


def test_report_api_lists_and_downloads(
    client: FlaskClient, app: Flask, tmp_path: Path
) -> None:
    app.config["REPORT_STORAGE_DIR"] = str(tmp_path / "reports")
    _login_analyst(client, app)

    created = client.post(
        "/api/v1/reports",
        json={"report_type": "daily_summary", "parameters": {"format": "json"}},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    assert created.status_code == 202
    report_id = created.get_json()["report_id"]
    job_id = created.get_json()["job_id"]

    with app.app_context():
        execute_report(job_id)

    detail = client.get(f"/api/v1/reports/{report_id}")
    assert detail.status_code == 200
    assert detail.get_json()["report"]["status"] == "completed"

    listing = client.get("/api/v1/reports")
    assert listing.status_code == 200
    assert listing.get_json()["total"] == 1

    download = client.get(f"/api/v1/reports/{report_id}/download")
    assert download.status_code == 200
    assert download.content_type.startswith("application/json")
    assert b"hosts" in download.data


def test_download_before_completion_is_rejected(
    client: FlaskClient, app: Flask, tmp_path: Path
) -> None:
    app.config["REPORT_STORAGE_DIR"] = str(tmp_path / "reports")
    _login_analyst(client, app)

    created = client.post(
        "/api/v1/reports",
        json={"report_type": "daily_summary", "parameters": {}},
        headers={"X-CSRF-Token": csrf_token(client)},
    )
    report_id = created.get_json()["report_id"]

    download = client.get(f"/api/v1/reports/{report_id}/download")
    assert download.status_code == 409
    assert download.get_json()["error"]["code"] == "report_not_ready"
