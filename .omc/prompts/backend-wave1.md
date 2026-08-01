# Backend wave 1 task

Work only in `C:\Users\33185\Desktop\毕业设计\fan\.omc\worktrees\hostguard\backend` on branch `codex/hostguard-backend`.
Do not edit root contracts or files outside `backend/**`.

Build the production-quality Flask backend foundation for HostGuard:

- Create an installable Python 3.11 package under `backend/` using Flask 3, SQLAlchemy 2, Flask-Migrate/Alembic, Pydantic 2, Argon2 and cryptography.
- App factory, environment configuration, request IDs, structured JSON errors, security headers, SQLite default and PostgreSQL-compatible models.
- Models and migrations for User, WebSession, AuditLog, Host, AgentCredential, EnrollmentToken, AgentNonce, MetricSample, InventorySnapshot, ProcessSnapshot, ListeningPortSnapshot, SecurityEvent, FileChange, BaselineResult, DetectionRule, Alert, AlertTransition, BackgroundJob, NotificationChannel, NotificationDelivery and ReportJob. UUID string IDs and UTC timestamps.
- Browser auth endpoints `/api/v1/auth/csrf`, login, logout, me. Use random server-side sessions stored hashed, HttpOnly/SameSite cookies, CSRF on writes, Argon2id, login throttling. Seed/create admin only through CLI, never hardcode credentials.
- Server-side roles admin/analyst/viewer and reusable decorators. Implement user CRUD, audit list, host list/detail, dashboard summary, rule list/update, alert list/detail/transition skeletons with real database queries and pagination.
- Agent enrollment endpoint, signed policy endpoint, and signed batch ingestion matching `contracts/telemetry.schema.json`. HMAC canonical string is in `contracts/conventions.md`; reject >5 minute skew and nonce reuse; batch/event IDs must be idempotent.
- Input limits, explicit exception handling and no secret values in responses/logs.
- Add focused pytest tests for auth, CSRF, RBAC, enrollment, HMAC/replay, ingestion idempotency, pagination and error envelopes. Target >=80% for implemented services.

Run tests and lint/type checks that are feasible. Commit all changes to your branch with clear commits. Report commit SHA, commands and failures to the parent. Do not spawn subagents.

