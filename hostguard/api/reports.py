from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Blueprint, g, jsonify, request, send_file

from ..authz import require_auth, require_role, write_audit
from ..errors import ApiError
from ..extensions import db
from ..models import BackgroundJob, ReportJob
from ..schemas import PaginationInput, ReportCreateInput
from . import paginate

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


@bp.get("")
@require_auth
def list_reports() -> tuple[Any, int]:
    params = PaginationInput.model_validate(
        {"page": request.args.get("page", 1), "page_size": request.args.get("page_size", 20)}
    )
    query = ReportJob.query
    status = request.args.get("status")
    if status:
        query = query.filter(ReportJob.status == status)
    total = query.count()
    items = (
        query.order_by(ReportJob.created_at.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
        .all()
    )
    return paginate([report.to_dict() for report in items], params.page, params.page_size, total)


@bp.get("/<report_id>")
@require_auth
def get_report(report_id: str) -> tuple[Any, int]:
    report = db.session.get(ReportJob, report_id)
    if report is None:
        raise ApiError("report_not_found", "The report was not found.", 404)
    return jsonify({"report": report.to_dict()}), 200


@bp.get("/<report_id>/download")
@require_role("admin", "analyst")
def download_report(report_id: str) -> Any:
    report = db.session.get(ReportJob, report_id)
    if report is None:
        raise ApiError("report_not_found", "The report was not found.", 404)
    if report.status != "completed" or not report.file_path:
        raise ApiError("report_not_ready", "The report is not ready for download.", 409)
    path = Path(report.file_path)
    if not path.exists():
        raise ApiError("report_file_missing", "The report file is missing.", 404)
    mimetype = "text/csv" if path.suffix.lower() == ".csv" else "application/json"
    return send_file(
        path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"report-{report.id}{path.suffix}",
    )
