from __future__ import annotations

from typing import Any

from flask import Blueprint, g, jsonify, request

from ..authz import require_auth, require_role, write_audit
from ..errors import ApiError
from ..extensions import db
from ..models import DetectionRule
from ..schemas import PaginationInput, RuleUpdateInput
from . import paginate

bp = Blueprint("rules", __name__, url_prefix="/api/v1/rules")


@bp.get("")
@require_auth
def list_rules() -> tuple[Any, int]:
    params = PaginationInput.model_validate(
        {"page": request.args.get("page", 1), "page_size": request.args.get("page_size", 20)}
    )
    total = DetectionRule.query.count()
    items = (
        DetectionRule.query.order_by(DetectionRule.name)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
        .all()
    )
    return paginate([rule.to_dict() for rule in items], params.page, params.page_size, total)


@bp.patch("/<rule_id>")
@require_role("admin")
def update_rule(rule_id: str) -> tuple[Any, int]:
    payload = RuleUpdateInput.model_validate(request.get_json(silent=True) or {})
    rule = db.session.get(DetectionRule, rule_id)
    if rule is None:
        raise ApiError("rule_not_found", "The rule was not found.", 404)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    rule.updated_by_user_id = g.current_user.id
    write_audit("rule.update", "rule", rule.id)
    db.session.commit()
    return jsonify({"rule": rule.to_dict()}), 200
