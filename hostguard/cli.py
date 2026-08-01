from __future__ import annotations

import os
from datetime import timedelta

import click
from flask import Flask

from .extensions import db
from .models import EnrollmentToken, User, utcnow
from .security import generate_token, hash_token


def register_cli(app: Flask) -> None:
    @app.cli.command("create-admin")
    @click.option("--username", required=True, help="Administrator username")
    @click.option("--email", required=True, help="Administrator email")
    @click.option(
        "--password",
        default=None,
        help="Password. Falls back to $HOSTGUARD_ADMIN_PASSWORD, then prompts.",
    )
    def create_admin(username: str, email: str, password: str | None) -> None:
        """Create the first administrator. Passwords are never hardcoded."""
        existing = User.query.filter(
            (User.username == username.lower()) | (User.email == email.lower())
        ).first()
        if existing is not None:
            raise click.ClickException(
                f"a user with username '{username}' or email '{email}' already exists"
            )

        secret = password or os.environ.get("HOSTGUARD_ADMIN_PASSWORD")
        if secret is None:
            secret = click.prompt(
                "Admin password", hide_input=True, confirmation_prompt=True
            )
        if len(secret) < 12:
            raise click.ClickException("password must be at least 12 characters")

        user = User(username=username, email=email, role="admin")
        user.set_password(secret)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created admin user '{username}' with role 'admin'.")

    @app.cli.command("create-enrollment-token")
    @click.option("--expires-hours", default=24, show_default=True, type=int)
    def create_enrollment_token(expires_hours: int) -> None:
        """Generate a one-time token agents use to enroll and receive a secret."""
        if expires_hours < 1 or expires_hours > 8760:
            raise click.ClickException("expires-hours must be between 1 and 8760")
        token = generate_token()
        db.session.add(
            EnrollmentToken(
                token_hash=hash_token(token),
                expires_at=utcnow() + timedelta(hours=expires_hours),
            )
        )
        db.session.commit()
        click.echo(token)

    @app.cli.command("run-workers")
    @click.option("--once", is_flag=True, help="Run a single pass and exit.")
    def run_workers(once: bool) -> None:
        """Run one maintenance pass: host status, rule evaluation, reports, notifications."""
        from .host_status import refresh_host_statuses
        from .notifications import process_deliveries
        from .reporting import run_pending_report_jobs
        from .rule_engine import run_rule_evaluation

        click.echo("refreshing host statuses...")
        refresh_host_statuses()
        click.echo("evaluating detection rules...")
        run_rule_evaluation()
        click.echo("executing report jobs...")
        run_pending_report_jobs()
        click.echo("delivering notifications...")
        process_deliveries()
        click.echo("workers pass complete.")
