from __future__ import annotations

import csv
import io
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from flask import current_app
from sqlalchemy import func

from .extensions import db
from .models import (
    Alert,
    BackgroundJob,
    Host,
    ReportJob,
    SecurityEvent,
    isoformat_utc,
    utcnow,
)

REPORT_TYPES = ("daily_summary", "alert_report", "host_report")
REPORT_EXPIRY_DAYS = 7


def execute_report(job_id: str) -> ReportJob | None:
    """Run a report background job. Transitions pending->running->completed/failed."""
    job = db.session.get(BackgroundJob, job_id)
    if job is None or job.status not in ("pending", "running"):
        return None
    report: ReportJob | None = ReportJob.query.filter_by(job_id=job.id).first()
    if report is None:
        return None

    job.status = "running"
    job.started_at = utcnow()
    report.status = "running"
    db.session.commit()

    try:
        content = _build_report_content(report)
        file_path = _write_report_file(report, content)
        report.file_path = file_path
        report.status = "completed"
        report.expires_at = utcnow() + timedelta(days=REPORT_EXPIRY_DAYS)
        job.status = "completed"
        job.finished_at = utcnow()
        job.error = None
    except Exception as exc:  # noqa: BLE001 - job failures are recorded, not raised
        db.session.rollback()
        job.status = "failed"
        job.finished_at = utcnow()
        job.error = str(exc)[:1000]
        report.status = "failed"
        report.file_path = None
    db.session.commit()
    return report


def run_pending_report_jobs() -> list[str]:
    """Execute every report job still pending/running; returns processed job ids."""
    jobs = (
        BackgroundJob.query.filter_by(job_type="report")
        .filter(BackgroundJob.status.in_(["pending", "running"]))
        .all()
    )
    processed = [job.id for job in jobs]
    for job in jobs:
        execute_report(job.id)
    return processed


def _build_report_content(report: ReportJob) -> dict[str, Any]:
    report_type = report.report_type
    if report_type not in REPORT_TYPES:
        raise ValueError(f"unsupported report type: {report_type}")
    parameters = report.parameters or {}
    scope = parameters.get("scope", "all")
    days = max(1, min(int(parameters.get("days", 7)), 90))

    if report_type == "daily_summary":
        return _summary_content(scope, days)
    if report_type == "alert_report":
        return _alert_report_content(scope, days, parameters.get("severity"))
    return _host_report_content(scope)


def _summary_content(scope: str, days: int) -> dict[str, Any]:
    hosts_query = Host.query
    alerts_query = Alert.query
    events_query = SecurityEvent.query
    if scope not in (None, "", "all"):
        hosts_query = hosts_query.filter_by(id=scope)
        alerts_query = alerts_query.filter_by(host_id=scope)
        events_query = events_query.filter_by(host_id=scope)

    hosts_by_status = {
        status: int(count)
        for status, count in hosts_query.with_entities(Host.status, func.count(Host.id))
        .group_by(Host.status)
        .all()
    }
    alerts_by_status = {
        status: int(count)
        for status, count in alerts_query.with_entities(Alert.status, func.count(Alert.id))
        .group_by(Alert.status)
        .all()
    }
    alerts_by_severity = {
        severity: int(count)
        for severity, count in alerts_query.with_entities(
            Alert.severity, func.count(Alert.id)
        )
        .group_by(Alert.severity)
        .all()
    }
    recent_events = events_query.order_by(SecurityEvent.occurred_at.desc()).limit(20).all()
    return {
        "generated_at": isoformat_utc(utcnow()),
        "scope": scope,
        "hosts": {
            "total": sum(hosts_by_status.values()),
            "by_status": hosts_by_status,
        },
        "alerts": {
            "total": sum(alerts_by_status.values()),
            "by_status": alerts_by_status,
            "by_severity": alerts_by_severity,
        },
        "events": {
            "total": events_query.count(),
            "recent": [
                {
                    "id": event.id,
                    "event_type": event.event_type,
                    "severity": event.severity,
                    "summary": event.summary,
                    "occurred_at": isoformat_utc(event.occurred_at),
                }
                for event in recent_events
            ],
        },
        "risk_trend": _risk_trend(scope, days),
    }


def _alert_report_content(scope: str, days: int, severity: str | None) -> dict[str, Any]:
    query = Alert.query
    if scope not in (None, "", "all"):
        query = query.filter_by(host_id=scope)
    if severity:
        query = query.filter(Alert.severity == severity)
    since = utcnow() - timedelta(days=days)
    query = query.filter(Alert.first_seen_at >= since)
    alerts = query.order_by(Alert.first_seen_at.desc()).all()
    return {
        "generated_at": isoformat_utc(utcnow()),
        "scope": scope,
        "days": days,
        "severity_filter": severity,
        "alerts": [alert.to_dict() for alert in alerts],
    }


def _host_report_content(scope: str) -> dict[str, Any]:
    query = Host.query
    if scope not in (None, "", "all"):
        query = query.filter_by(id=scope)
    hosts = query.order_by(Host.hostname).all()
    return {
        "generated_at": isoformat_utc(utcnow()),
        "scope": scope,
        "hosts": [host.to_dict() for host in hosts],
    }


def _risk_trend(scope: str, days: int) -> list[dict[str, Any]]:
    start = (utcnow() - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    query = db.session.query(func.date(Alert.first_seen_at), func.count(Alert.id))
    if scope not in (None, "", "all"):
        query = query.filter(Alert.host_id == scope)
    counts = {
        str(day): int(count)
        for day, count in query.filter(Alert.first_seen_at >= start)
        .group_by(func.date(Alert.first_seen_at))
        .all()
    }
    trend = []
    for offset in range(days):
        day = (start + timedelta(days=offset)).date().isoformat()
        trend.append({"date": day, "count": counts.get(day, 0)})
    return trend


def _write_report_file(report: ReportJob, content: dict[str, Any]) -> str:
    storage = Path(current_app.config["REPORT_STORAGE_DIR"])
    storage.mkdir(parents=True, exist_ok=True)
    fmt = (report.parameters or {}).get("format", "json")
    ext = "csv" if fmt == "csv" else "json"
    path = storage / f"{report.id}.{ext}"
    if fmt == "csv":
        path.write_text(_content_to_csv(content), encoding="utf-8")
    else:
        path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path.as_posix()


def _content_to_csv(content: dict[str, Any]) -> str:
    """Flatten report content into CSV rows, preferring the first table-like list."""
    table = None
    for value in content.values():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            table = value
            break
    buffer = io.StringIO()
    if table is None:
        writer = csv.DictWriter(buffer, fieldnames=sorted(content.keys()))
        writer.writeheader()
        writer.writerow(
            {key: json.dumps(value, ensure_ascii=False) for key, value in content.items()}
        )
    else:
        fieldnames = sorted({key for row in table for key in row.keys()})
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in table:
            writer.writerow(row)
    return buffer.getvalue()
