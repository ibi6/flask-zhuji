# HostGuard shared conventions

All identifiers are UUID strings. All timestamps use UTC ISO-8601 with a trailing `Z`.
The API prefix is `/api/v1`. Browser authentication uses an HttpOnly session cookie and
an `X-CSRF-Token` header on mutating requests. Agent requests are authenticated separately.

## Enumerations

- Roles: `admin`, `analyst`, `viewer`
- Host source: `real`, `simulated`
- Host status: `online`, `degraded`, `offline`
- Severity: `low`, `medium`, `high`, `critical`
- Alert status: `open`, `investigating`, `resolved`, `ignored`
- Delivery status: `pending`, `retrying`, `sent`, `failed`
- Report status: `pending`, `running`, `completed`, `failed`, `expired`

## Error and pagination envelopes

Errors use `{"error":{"code":"...","message":"...","details":{},"request_id":"uuid"}}`.
Paginated responses use `{"items":[],"page":1,"page_size":20,"total":0}`.

## Agent signing

Signed requests include `X-HG-Agent-Id`, `X-HG-Timestamp`, `X-HG-Nonce`, and
`X-HG-Signature`. The lowercase hexadecimal signature is HMAC-SHA256 over:

```text
timestamp\nnonce\nMETHOD\n/path\nsha256_hex(raw_body)
```

The server accepts at most five minutes of clock skew and stores nonces for ten minutes.
Enrollment uses a one-time token and returns an agent secret exactly once.

## Role permissions

- `admin`: all resources, user management, rule and notification configuration.
- `analyst`: read telemetry, investigate alerts, create and download reports.
- `viewer`: read dashboards, hosts, alerts, rules, reports, and audit events only.

