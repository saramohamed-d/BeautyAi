# Architecture

## Guiding principle: workflow-first, not agent-first

BeautyAI uses LLMs where language understanding, extraction, or reasoning
add real value (intent classification, structured extraction from Arabic
input, summarization, tool selection). Everything else — filtering,
validation, business rules, doctor ranking, pricing, availability,
booking, authorization — is deterministic backend code. See the root
prompt / product spec for the full rationale; this file tracks how the
codebase implements it sprint by sprint.

## Sprint 0 scope

Sprint 0 builds the skeleton only: no agents, no LangGraph, no RAG, no
booking logic, no auth logic beyond a JWT config placeholder. Its job is
to make Sprints 1+ fast and safe to build by getting the following right
once:

- **Docker Compose** orchestrating Postgres (pgvector-enabled image, used
  starting Sprint 8), Redis, backend, and frontend, with health-based
  startup ordering.
- **FastAPI skeleton**: `app/main.py` as a thin composition root;
  `app/core/config.py` as the single source of truth for environment
  configuration; `app/core/logging.py` for structured, contextual logs.
- **Async SQLAlchemy** engine/session (`app/db/session.py`) and Alembic
  wired to the same settings object, ready for Sprint 1 to add models.
- **Health check** (`GET /api/v1/health`) that actually pings Postgres and
  Redis — used both by developers and, later, by container orchestration.
- **Next.js skeleton** with the App Router, Tailwind (RTL-ready via
  logical utilities + native `dir` attribute), TanStack Query, and a
  services/hooks layer so components never call `fetch` directly.
- **Testing setup** on both sides (pytest + httpx ASGI client for the
  backend; frontend testing tools to be added when there's meaningful
  component logic to test, starting Sprint 4).

## Directory structure

See root `README.md` for the top-level tree. Backend packages
(`api`, `agents`, `workflows`, `rag`, `tools`, `services`, `models`,
`schemas`, `prompts`, `core`, `db`) are all created empty in Sprint 0 so
the intended architecture is visible from the file tree from day one,
even though most of them have no code yet.

## Sprint 1: database schema

Full ERD, relationship rationale, and constraint list now live in
[`docs/database.md`](database.md) (kept there so schema details aren't
duplicated across two docs). Summary of what changed vs. Sprint 0:

- 17 tables across 8 model modules (`app/models/*.py`), all UUID-keyed,
  all timestamped, wired into one initial Alembic migration.
- Every relationship required by the spec (patients → consents →
  conversations → messages/intakes; doctors ↔ clinics ↔ procedures;
  availability → appointments; knowledge documents → chunks; safety/audit
  logs) is modeled with explicit foreign keys, cascade rules, and — where
  the spec implies a hard business rule (no double-booking, no duplicate
  idempotent bookings, no duplicate doctor-procedure-clinic combos) — a
  `UNIQUE` or `CHECK` constraint enforced by Postgres itself, not just
  application code.
- Verified with: `alembic upgrade head` → `alembic downgrade base` →
  `alembic upgrade head` round trip (including enum type cleanup), a seed
  script producing realistic Egyptian clinic/doctor/patient data, and 12
  pytest tests that exercise cascades and constraint violations against a
  real Postgres instance.



- **i18n / locale routing strategy** (e.g. `/ar`, `/en` route prefixes vs.
  a single Arabic-first UI with an English toggle) — deferred to Sprint 3/4.
  Sprint 0's layout hardcodes `dir="rtl"` / `lang="ar"` as a placeholder.
- **Auth strategy details** (JWT vs. session cookies, refresh token
  rotation) — deferred to Sprint 2. Config placeholders exist now so the
  eventual shape doesn't require a breaking config change later.

## Sprint roadmap

| Sprint | Focus |
|---|---|
| 0 | Project foundation (this sprint) |
| 1 | Database foundation (models, migrations, seed data) |
| 2 | Backend API foundation (routes, services, auth foundation) |
| 3 | Frontend foundation (layout, nav, API client, auth UI) |
| 4 | Patient chat UI |
| 5 | LangGraph foundation (PatientState, graph, routing) |
| 6 | Intake agent |
| 7 | Safety agent |
| 8 | RAG ingestion |
| 9 | RAG retrieval |
| 10 | Analysis agent |
| 11 | Doctor/clinic matching |
| 12 | Doctor/clinic frontend |
| 13 | Availability |
| 14 | Booking |
| 15 | Clinic dashboard |
| 16 | Admin dashboard |
| 17 | WhatsApp integration |
| 18 | Follow-up / reminders |
| 19 | Evaluation |
| 20 | Production hardening |
