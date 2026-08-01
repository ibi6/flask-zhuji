from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError, model_validator

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")
ROLE_LITERAL = Literal["admin", "analyst", "viewer"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginInput(StrictModel):
    username: str = Field(min_length=3, max_length=64, pattern=USERNAME_PATTERN.pattern)
    password: str = Field(min_length=1, max_length=128)


class CreateUserInput(StrictModel):
    username: str = Field(min_length=3, max_length=64, pattern=USERNAME_PATTERN.pattern)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: ROLE_LITERAL

    @model_validator(mode="after")
    def validate_password_strength(self) -> CreateUserInput:
        password = self.password
        if not (
            any(character.islower() for character in password)
            and any(character.isupper() for character in password)
            and any(character.isdigit() for character in password)
        ):
            raise ValueError("password must include uppercase, lowercase, and numeric characters")
        return self


class UpdateUserInput(StrictModel):
    email: EmailStr | None = None
    role: ROLE_LITERAL | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> UpdateUserInput:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class PaginationInput(StrictModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AlertTransitionInput(StrictModel):
    status: Literal["open", "investigating", "resolved", "ignored"]
    reason: str | None = Field(default=None, max_length=1024)


class RuleUpdateInput(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    enabled: bool | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    criteria: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_change(self) -> RuleUpdateInput:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class ReportCreateInput(StrictModel):
    report_type: str = Field(min_length=1, max_length=64)
    parameters: dict[str, Any] = Field(default_factory=dict, max_length=64)


class NotificationChannelCreateInput(StrictModel):
    name: str = Field(min_length=1, max_length=128)
    channel_type: Literal["webhook", "email"]
    config: dict[str, Any] = Field(default_factory=dict, max_length=32)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_channel_config(self) -> NotificationChannelCreateInput:
        if self.channel_type == "webhook" and not self.config.get("url"):
            raise ValueError("webhook channels require a config.url")
        if self.channel_type == "email":
            recipients = self.config.get("recipients")
            if not self.config.get("host"):
                raise ValueError("email channels require a config.host")
            if not isinstance(recipients, list) or not recipients:
                raise ValueError("email channels require a config.recipients list")
        return self


class AgentEnrollInput(StrictModel):
    token: str = Field(min_length=8, max_length=256)
    hostname: str = Field(min_length=1, max_length=255)
    os: Literal["windows", "linux"]
    os_version: str = Field(default="", max_length=255)
    architecture: str = Field(default="", max_length=64)
    agent_version: str = Field(default="", max_length=32)


def validation_details(error: ValidationError) -> dict[str, Any]:
    return {
        "fields": error.errors(
            include_url=False,
            include_context=False,
            include_input=False,
        )
    }
