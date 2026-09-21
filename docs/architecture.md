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



- **i18n / locale routing strategy** — resolved in Sprint 4: English by
  default with a full Arabic (RTL) alternative, chosen by a cookie rather
  than `/en` `/ar` route prefixes. See [`docs/design.md`](design.md).
- **Auth strategy details** (JWT vs. session cookies, refresh token
  rotation) — deferred to Sprint 2. Config placeholders exist now so the
  eventual shape doesn't require a breaking config change later.

## Sprint roadmap

Reordered after Sprint 3 to follow the patient journey in
`BeautyAI_Product_System_Functionality_Spec.md` and the approved
interactive demo. Principles behind the order:

- Design system and English/Arabic come first, so every later screen is
  built once, already styled and translatable.
- Real accounts and permissions come before any AI, because
  conversations and bookings must belong to a user and every AI tool
  must check permissions.
- Deterministic booking rules come before the Booking Agent. The agent
  calls the same tested backend functions a person uses; it never owns
  booking logic.
- Safety ships in the first AI sprint, not at the end.

| Sprint | Focus | Status |
|---|---|---|
| 0 | Infrastructure (Docker, FastAPI, Next.js skeletons, health checks) | Done |
| 1 | Database schema, migrations, seed data | Done |
| 2 | Backend CRUD APIs | Done |
| 3 | Frontend foundation (pages, API client, booking wizard) | Done |
| **Phase 1: solid base** | | |
| 4 | Design system from the demo + English/Arabic (RTL) switch | Done |
| 5 | Real accounts: `users` table, email/phone + password, roles (patient, doctor, clinic admin, platform admin), backend RBAC on every endpoint; plan bilingual content fields | Done |
| 6 | Booking rules: fix slot re-booking after cancel and concurrent-booking 500s, temporary slot hold during payment, cancel/reschedule policy, doctor search API | Done |
| **Phase 2: AI** | | |
| 7 | AI chat + safety: chat UI, conversation API, LLM orchestration, red-flag detection and "not a diagnosis" guardrails from day one | Done |
| 8 | Medical knowledge (RAG): approved content, pgvector retrieval, citations, EN + AR | Done |
| 9 | AI consultation: follow-up questions → preliminary assessment → suggested specialty (replaces the fixed lookup in `frontend/lib/concerns.ts`) | Done |
| 10 | Matching + Booking Agent: agent calls the Sprint 6 tools, always asks for explicit confirmation (replaces the deterministic search in `frontend/app/assistant`) | Done |
| **Phase 3: money and providers** | | |
| 11 | Payments: card / mobile wallet via Paymob, pay at clinic, webhook-confirmed bookings, automatic refunds (InstaPay not offered, see `docs/payments.md`) | Done |
| 12 | Doctor sign-up + verification: documents, admin approve/reject, doctor dashboard (the admin *screen* lands in Sprint 14) | Done |
| 13 | Clinic admin dashboard: doctors, services, prices, hours, slots, appointments | Done |
| 14 | Platform admin dashboard: users, verification, payments, reports, audit logs | Done |
| **Phase 4: launch** | | |
| 15 | Notifications + follow-up: reminders and aftercare (email / SMS / WhatsApp) | Done |
| 16 | AI evaluation: EN + AR test conversations, safety and accuracy metrics | Done |
| 17 | Security, privacy (Egypt PDPL review), production deployment | Done |
