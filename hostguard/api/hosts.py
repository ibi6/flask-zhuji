from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from ..authz import require_auth
from ..errors import ApiError
from ..extensions import db
from ..host_status import refresh_host_statuses
from ..models import Host, InventorySnapshot, MetricSample, isoformat_utc
from ..schemas import PaginationInput
from . import paginate

bp = Blueprint("hosts", __name__, url_prefix="/api/v1/hosts")


@bp.get("")
@require_auth
def list_hosts() -> tuple[Any, int]:
    refresh_host_statuses()
    params = PaginationInput.model_validate(
        {"page": request.args.get("page", 1), "page_size": request.args.get("page_size", 20)}
    )
    query = Host.query
    status = request.args.get("status")
    source = request.args.get("source")
    if status:
        query = query.filter(Host.status == status)
    if source:
        query = query.filter(Host.source == source)
    total = query.count()
    items = (
        query.order_by(Host.hostname)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
        .all()
    )
    return paginate([host.to_dict() for host in items], params.page, params.page_size, total)


@bp.get("/<host_id>")
@require_auth
def get_host(host_id: str) -> tuple[Any, int]:
    refresh_host_statuses()
    host = db.session.get(Host, host_id)
    if host is None:
        raise ApiError("host_not_found", "The host was not found.", 404)

    recent_metric = (
        MetricSample.query.filter_by(host_id=host_id)
        .order_by(MetricSample.collected_at.desc())
        .first()
    )
    inventory = (
        InventorySnapshot.query.filter_by(host_id=host_id)
        .order_by(InventorySnapshot.created_at.desc())
        .first()
    )
    data = host.to_dict()
    if recent_metric is not None:
        data["last_metric"] = {
            "collected_at": isoformat_utc(recent_metric.collected_at),
            "cpu_percent": recent_metric.cpu_percent,
            "memory_percent": recent_metric.memory_percent,
            "disk_percent": recent_metric.disk_percent,
            "network_bytes_sent": recent_metric.network_bytes_sent,
            "network_bytes_recv": recent_metric.network_bytes_recv,
        }
    else:
        data["last_metric"] = None
    data["inventory"] = (
        {
            "hostname": inventory.hostname,
            "os": inventory.os,
            "os_version": inventory.os_version,
            "architecture": inventory.architecture,
            "agent_version": inventory.agent_version,
            "boot_time": isoformat_utc(inventory.boot_time),
            "ip_addresses": inventory.ip_addresses,
        }
        if inventory is not None
        else None
    )
    return jsonify({"host": data}), 200
