from __future__ import annotations

from typing import Any

from flask import Blueprint, g, jsonify, request

from ..authz import require_role, write_audit
from ..extensions import db
from ..models import BackgroundJob, ReportJob
from ..schemas import ReportCreateInput

bp = Blueprint("reports", __name__, url_prefix="/api/v1/reports")


@bp.post("")
@require_role("admin", "analyst")
def create_report() -> tuple[Any, int]:
    payload = ReportCreateInput.model_validate(request.get_json(silent=True) or {})
    job = BackgroundJob(
        job_type="report",
        status="pending",
        payload={"report_type": payload.report_type, "parameters": payload.parameters},
        created_by_user_id=g.current_user.id,
    )
    db.session.add(job)
    db.session.flush()
    report = ReportJob(
        job_id=job.id,
        report_type=payload.report_type,
        parameters=payload.parameters,
        status="pending",
    )
    db.session.add(report)
    write_audit("report.create", "report", report.id)
    db.session.commit()
    return jsonify({"report_id": report.id, "job_id": job.id, "status": report.status}), 202
