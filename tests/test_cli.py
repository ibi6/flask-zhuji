from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient, FlaskCliRunner

from hostguard.extensions import db
from hostguard.models import EnrollmentToken, User


def test_create_admin_via_cli(app: Flask) -> None:
    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(
        args=[
            "create-admin",
            "--username",
            "rootadmin",
            "--email",
            "root@example.com",
            "--password",
            "Root-Admin-Password-42",
        ]
    )
    assert result.exit_code == 0, result.output
    with app.app_context():
        user = User.query.filter_by(username="rootadmin").one()
        assert user.role == "admin"
        assert user.email == "root@example.com"
        assert user.verify_password("Root-Admin-Password-42")


def test_create_admin_rejects_duplicate(app: Flask, client: FlaskClient) -> None:
    with app.app_context():
        user = User(username="dup", email="dup@example.com", role="admin")
        user.set_password("Duplicate-Password-42")
        db.session.add(user)
        db.session.commit()

    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(
        args=[
            "create-admin",
            "--username",
            "dup",
            "--email",
            "other@example.com",
            "--password",
            "Duplicate-Password-42",
        ]
    )
    assert result.exit_code != 0


def test_create_admin_rejects_short_password(app: Flask) -> None:
    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(
        args=[
            "create-admin",
            "--username",
            "rootadmin",
            "--email",
            "root@example.com",
            "--password",
            "short",
        ]
    )
    assert result.exit_code != 0


def test_create_enrollment_token_via_cli(app: Flask) -> None:
    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(args=["create-enrollment-token", "--expires-hours", "2"])
    assert result.exit_code == 0, result.output
    token = result.output.strip()
    assert token
    with app.app_context():
        assert EnrollmentToken.query.count() == 1
        from hostguard.security import hash_token

        stored = EnrollmentToken.query.one()
        assert stored.token_hash == hash_token(token)
