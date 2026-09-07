# Security & Privacy

## Sprint 0 posture

- All secrets (DB credentials, JWT secret, OpenAI key) are read from
  environment variables via `app/core/config.py` — never hardcoded, never
  committed (`.env` is gitignored; `.env.example` documents the shape
  with placeholder values).
- CORS is explicitly configured (`app/main.py`) rather than left wide open.
- No authentication/authorization exists yet — the only endpoints
  (`/`, `/api/v1/health`) intentionally require none, since health checks
  must be reachable before any identity exists.

## Deferred to later sprints

- Authentication, RBAC (PATIENT / DOCTOR / CLINIC_ADMIN / SUPER_ADMIN) — Sprint 2+
- Rate limiting, input validation hardening, audit logging — Sprint 20
- PII minimization, log redaction, configurable data retention — ongoing,
  finalized in Sprint 20
- Explicit patient consent flow — Sprint 6 (Intake) / Sprint 1 (schema)

**Legal note:** this project does not, on its own, guarantee compliance
with Egyptian or regional healthcare data protection law. Legal review is
required before handling real patient data in production — flagged here
per the project's "no automatic legal compliance" rule.
