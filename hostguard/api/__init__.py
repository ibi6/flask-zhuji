from __future__ import annotations

from typing import Any

from flask import jsonify


def paginate(
    items: list[dict[str, Any]], page: int, page_size: int, total: int
) -> tuple[Any, int]:
    return jsonify({"items": items, "page": page, "page_size": page_size, "total": total}), 200
