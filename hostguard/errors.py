from __future__ import annotations

from typing import Any

from flask import Flask, Response, g, jsonify
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from .extensions import db
from .schemas import validation_details


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _request_id() -> str:
    return getattr(g, "request_id", "")


def error_response(
    code: str, message: str, status_code: int, details: dict[str, Any] | None = None
) -> tuple[Response, int]:
    return (
        jsonify(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                    "request_id": _request_id(),
                }
            }
        ),
        status_code,
    )


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError) -> tuple[Response, int]:
        if error.status_code >= 500:
            app.logger.error(
                "api_error",
                extra={"request_id": _request_id(), "error_code": error.code},
            )
        return error_response(error.code, error.message, error.status_code, error.details)

    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError) -> tuple[Response, int]:
        return error_response(
            "validation_error",
            "The request payload is invalid.",
            422,
            validation_details(error),
        )

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error: SQLAlchemyError) -> tuple[Response, int]:
        db.session.rollback()
        app.logger.exception("database_error", extra={"request_id": _request_id()})
        return error_response("database_error", "A database error occurred.", 500)

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException) -> tuple[Response, int]:
        mapping = {
            400: ("bad_request", "The request could not be processed."),
            401: ("unauthorized", "Authentication is required."),
            403: ("forbidden", "You do not have permission to perform this action."),
            404: ("not_found", "The requested resource was not found."),
            405: ("method_not_allowed", "The request method is not allowed."),
            413: ("payload_too_large", "The request payload is too large."),
            415: ("unsupported_media_type", "The request content type is not supported."),
            429: ("rate_limit_exceeded", "Too many requests. Try again later."),
        }
        code, message = mapping.get(
            error.code or 500, ("http_error", "The request could not be processed.")
        )
        return error_response(code, message, error.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception) -> tuple[Response, int]:
        app.logger.exception("unexpected_error", extra={"request_id": _request_id()})
        return error_response("internal_error", "An unexpected error occurred.", 500)

