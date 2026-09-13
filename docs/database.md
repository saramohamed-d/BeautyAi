# Database

## Status: Sprint 1 complete

17 tables, all under Alembic version control. Schema defined in
`backend/app/models/`, one module per domain area:

| Module | Tables |
|---|---|
| `patient.py` | `patients`, `patient_consents` |
| `conversation.py` | `conversations`, `messages`, `intakes` |
| `doctor.py` | `doctors`, `doctor_credentials` |
| `clinic.py` | `clinics`, `clinic_staff` |
| `procedure.py` | `procedures`, `doctor_procedures` |
| `scheduling.py` | `availability`, `appointments` |
| `knowledge.py` | `knowledge_documents`, `knowledge_chunks` |
| `audit.py` | `audit_events`, `safety_events` |

## Conventions

- **Primary keys**: UUID, generated in Postgres via `gen_random_uuid()`
  (pgcrypto extension, enabled in the initial migration) — see
  `app/models/base.py::UUIDPkMixin`.
- **Timestamps**: every table has `created_at`/`updated_at` via
  `TimestampMixin`, except `messages` and `audit_events`, which are
  intentionally immutable (`created_at` only, no `updated_at`).
- **Enums**: native Postgres `ENUM` types (not varchar) for closed value
  sets — `appointment_status`, `risk_level`, `verification_status`, etc.
  Adding a new value requires a migration (`ALTER TYPE ... ADD VALUE`).
- **JSONB** is used for genuinely open-ended/evolving shapes only:
  `intakes.structured_data`, `messages.extra_data`,
  `safety_events.red_flags`, `audit_events.extra_data`.

## Key constraints enforced at the database level

- `appointments.availability_id` is `UNIQUE` → a slot can back at most
  one appointment (the double-booking guard).
- `appointments.idempotency_key` is `UNIQUE` → duplicate booking retries
  fail at INSERT instead of creating a second row.
- `intakes.conversation_id` is `UNIQUE` → enforces the 1:1 relationship
  with `conversations`.
- `doctor_procedures` has a composite `UNIQUE(doctor_id, procedure_id, clinic_id)`
  → the same doctor can offer the same procedure at multiple clinics, but
  not register it twice at the same clinic.
- `CHECK` constraints: `availability.end_time > start_time`,
  `appointments.scheduled_end > scheduled_start`,
  `doctor_procedures.price >= 0`.

See `docs/architecture.md` for the full ERD and relationship rationale.

## Migrations

```bash
cd backend
alembic current              # show applied revision
alembic history --verbose    # show all revisions
alembic upgrade head         # apply all pending migrations
alembic downgrade base       # roll back to empty schema
alembic revision --autogenerate -m "description"   # generate a new migration after model changes
```

The initial migration (`alembic/versions/7867ecd1f62c_initial_schema.py`)
creates the pgcrypto extension, all 17 tables, all enums, all indexes and
constraints — and its `downgrade()` explicitly drops the enum types too
(autogenerate only emits `DROP TABLE`, not `DROP TYPE`), verified with a
full upgrade → downgrade → upgrade round trip.

## Seed data

```bash
cd backend
python -m app.db.seed
```

Wipes and re-inserts a fixed, realistic dataset: 3 Cairo/Giza clinics, 3
doctors (2 verified, 1 pending), doctor credentials, clinic-staff
memberships, 4 procedures with per-clinic pricing, ~27 availability
slots, 2 patients with consents, a normal Egyptian-Arabic intake
conversation, a high-risk conversation with a `safety_events` row, one
confirmed appointment, and one approved knowledge document with 2 chunks
(no embeddings yet — that's Sprint 8).
