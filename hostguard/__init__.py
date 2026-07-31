from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from flask import Flask, Response, g, jsonify, request

from .config import Config, validate_config
from .errors import register_error_handlers
from .extensions import db, limiter, migrate
from .logging_config import configure_logging
from .security import require_csrf

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def create_app(config_overrides: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)
    validate_config(app.config)

    _ensure_sqlite_directory(app.config["SQLALCHEMY_DATABASE_URI"])

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    configure_logging(app)

    _register_request_id(app)
    _register_security_headers(app)
    _register_browser_guards(app)
    register_error_handlers(app)
    _register_health_endpoints(app)
    _register_blueprints(app)
    _register_cli(app)
    return app


def _ensure_sqlite_directory(database_uri: str) -> None:
    if database_uri.startswith("sqlite:///"):
        path = database_uri.removeprefix("sqlite:///")
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)


def _register_request_id(app: Flask) -> None:
    @app.before_request
    def set_request_id() -> None:
        incoming = request.headers.get("X-Request-ID", "")
        g.request_id = incoming if _is_valid_uuid(incoming) else str(uuid4())

    @app.after_request
    def attach_request_id(response: Response) -> Response:
        response.headers["X-Request-ID"] = str(getattr(g, "request_id", ""))
        return response


def _register_security_headers(app: Flask) -> None:
    @app.after_request
    def security_headers(response: Response) -> Response:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        if app.config["SESSION_COOKIE_SECURE"]:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        if request.path.startswith("/api/v1/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


def _register_browser_guards(app: Flask) -> None:
    @app.before_request
    def csrf_protection() -> None:
        path = request.path
        if (
            request.method in MUTATING_METHODS
            and path.startswith("/api/v1/")
            and not path.startswith("/api/v1/agent/")
        ):
            require_csrf()

    @app.before_request
    def load_current_user() -> None:
        g.current_user = None
        if request.path.startswith("/api/v1/"):
            from .authz import load_user_from_request

            g.current_user = load_user_from_request()


def _register_health_endpoints(app: Flask) -> None:
    @app.get("/health/live")
    def health_live() -> tuple[Response, int]:
        return jsonify({"status": "ok"}), 200

    @app.get("/health/ready")
    def health_ready() -> tuple[Response, int]:
        return jsonify({"status": "ready"}), 200


def _register_blueprints(app: Flask) -> None:
    from .api.agent import bp as agent_bp
    from .api.alerts import bp as alerts_bp
    from .api.audit import bp as audit_bp
    from .api.auth import bp as auth_bp
    from .api.dashboard import bp as dashboard_bp
    from .api.hosts import bp as hosts_bp
    from .api.reports import bp as reports_bp
    from .api.rules import bp as rules_bp
    from .api.users import bp as users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(hosts_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(rules_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(agent_bp)


def _register_cli(app: Flask) -> None:
    from .cli import register_cli

    register_cli(app)


def _is_valid_uuid(value: str) -> bool:
    try:
        return str(UUID(value)) == value
    except (ValueError, AttributeError, TypeError):
        return False


__all__ = ["create_app", "db", "Config"]
