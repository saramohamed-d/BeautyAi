# Database

## Status: Sprint 8 complete

19 tables, all under Alembic version control. Schema defined in
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
| `user.py` | `users`, `refresh_tokens` (Sprint 5) |

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

- Partial unique index `uq_appointments_active_availability` on
  `appointments.availability_id WHERE status <> 'cancelled'` → a slot backs
  at most one *active* appointment (the double-booking guard), while a
  cancelled slot can be booked again and the cancelled appointment keeps
  its slot link for history. (Sprints 1–5 used a plain `UNIQUE`, which made
  cancelled slots impossible to rebook.)
- `clinics.cancellation_cutoff_hours >= 0` (CHECK).
- `appointments.idempotency_key` is `UNIQUE` → duplicate booking retries
  fail at INSERT instead of creating a second row.
- `intakes.conversation_id` is `UNIQUE` → enforces the 1:1 relationship
  with `conversations`.
- `doctor_procedures` has a composite `UNIQUE(doctor_id, procedure_id, clinic_id)`
  → the same doctor can offer the same procedure at multiple clinics, but
  not register it twice at the same clinic.
- `users.email` and `users.phone` are each `UNIQUE`, and
  `CHECK (email IS NOT NULL OR phone IS NOT NULL)` requires at least one.
- `patients.user_id` and `doctors.user_id` are `UNIQUE` (one account per
  profile); `clinic_staff` has `UNIQUE(clinic_id, user_id)` because one
  person can work at several clinics.
- `payments.idempotency_key`, `payments.provider_order_id` and
  `payments.appointment_id` are `UNIQUE`; `payment_events` has
  `UNIQUE(provider, event_key)` so a webhook is processed once;
  `payments.amount >= 0` (CHECK).
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

## Notifications (Sprint 15)

Migration `1aa2d8927438_notifications`:

- `notifications` — one row per message: who it's for, channel, status,
  template, language, the address it went to, the rendered subject and
  body, what it was about (`appointment_id`), when it's due
  (`scheduled_for`), attempts, provider and its message id, and the
  error if it failed. `dedupe_key` is unique — the same reminder can
  never be written twice. Indexed on (status, scheduled_for): the
  sender's query.
- `patients.notify_email` / `notify_sms` / `notify_whatsapp` — the
  patient's channels (email and SMS default on, WhatsApp off).
- The table reuses the existing `language` enum rather than creating a
  second one.

See [`notifications.md`](notifications.md).

## Clinic hours (Sprint 13)

Migration `83a2477a2dbb_clinic_hours_and_slot_duration`:

- `clinic_hours` — one row per weekday per clinic (`weekday` 0-6,
  `opens_at`, `closes_at`, `is_closed`), unique per (clinic, weekday),
  with CHECKs for the weekday range and `closes_at > opens_at`. Times are
  clinic-local and stored without a zone.
- `clinics.slot_duration_minutes` — the default length of a generated
  slot (CHECK 5-240).

Nothing about booking changes: generated times are ordinary
`availability` rows. See [`clinic-admin.md`](clinic-admin.md).

## Doctor verification (Sprint 12)

Migration `cde6dcc397f6_doctor_verification`:

- `doctors`: sign-up fields (`sub_specialty`, `license_number`,
  `medical_degree`, `university`, `city`) and the review decision
  (`submitted_at`, `reviewed_at`, `reviewed_by_user_id`,
  `verification_notes`). `submitted_at IS NULL` means "not in the queue".
- `doctor_documents`: one row per uploaded file — type, status, original
  filename, `stored_path` (unique, relative to `UPLOAD_DIR`), content
  type, size, who uploaded it and the reviewer's note. The files
  themselves are never stored in the database.
- `audit_events` gets its first writers: `doctor.application_submitted`,
  `doctor.verified`, `doctor.rejected`.

See [`verification.md`](verification.md).

## Payments (Sprint 11)

Migration `7b73d61e3365_payments`:

- `clinic_staff.consultation_fee` — a doctor's fee at that clinic (EGP);
  null means the clinic confirms it and only "pay at clinic" is offered.
- `payments` — one row per checkout attempt: patient, slot, doctor,
  clinic, the appointment once booked, amount, currency, `method`
  (`card`/`wallet`/`pay_at_clinic`), `status`, `provider`
  (`paymob`/`demo`/`clinic`), the gateway's order and transaction ids,
  checkout URL, expiry, paid/refunded times and failure reason.
- `payment_events` — every gateway notification as received (JSON), for
  audit and duplicate detection.

See [`payments.md`](payments.md).

## Knowledge columns (Sprint 8)

- `knowledge_documents`: `slug` (unique, for re-ingestion), `summary`,
  `body` (full Markdown), `content_hash`, `reviewed_by`, `reviewed_at`.
- `knowledge_chunks`: `heading`, `language`, `embedding vector(1536)`
  (HNSW index, cosine), `embedding_model`, and `search_vector`, a
  generated `tsvector` using the Arabic or English analyzer by language
  (GIN index).

Migration `9a41c2e7d3b5_knowledge_rag.py` enables the `vector` extension
(shipped in the `pgvector/pgvector` Docker image). Details in [`rag.md`](rag.md).

## Booking columns (Sprint 6)

- `availability.held_by_patient_id`, `held_until`: a payment-step hold.
  A hold counts only while `held_until` is in the future.
- `appointments.cancellable_until`: deadline for patient changes, fixed at
  booking time from the clinic's policy. `cancelled_at`,
  `cancelled_by_user_id`, `cancellation_reason` record cancellations.
- `clinics.cancellation_cutoff_hours` (default 24): the clinic's policy.

Migration `56b733b79e88_booking_rules.py` backfills `cancellable_until`
for existing appointments.

## Accounts (Sprint 5)

`users` holds login identities only (email, phone, password hash, role,
status). Role-specific data stays in the profile tables, each linked back
with a nullable `user_id`:

```
users ──1:1── patients        (role = patient)
users ──1:1── doctors         (role = doctor)
users ──1:N── clinic_staff    (role = clinic_admin; one row per clinic managed)
users ──1:N── refresh_tokens  (one family per logged-in device)
```

Profiles can exist without a login (a clinic registering a walk-in
patient, a doctor listed before they join). Migration
`bc36cfae70a0_users_and_auth.py` also renames the audit actor type
`super_admin` to `platform_admin` to match the spec.

## Bilingual content: plan (not yet implemented)

The UI is English and Arabic (Sprint 4), but database text (doctor names
and bios, clinic names and descriptions, procedure names and
descriptions) is stored once, in whatever language it was entered in.

**Recommended approach: paired columns for display text.** For each
translatable field add an `_ar` twin, keeping the existing column as
English: `doctors.full_name` + `full_name_ar`, `bio` + `bio_ar`;
`clinics.name`/`name_ar`, `description`/`description_ar`, `address`/`address_ar`;
`procedures.name`/`name_ar`, `description`/`description_ar`.

- The API returns both; the frontend picks by locale and falls back to
  the other language when one is empty.
- Why columns, not a JSONB `{"en": ..., "ar": ...}` map or a separate
  translations table: only two languages are planned, columns are
  type-checked by the schema and easy to index and search, and there's
  no join on every catalog query. If a third language is ever needed,
  switch to a translations table then.
- Not translated: values that are codes, not text (`specialty`,
  `procedures.category`, `city`). The frontend already maps those to
  labels (`label("specialties", …)` in `lib/i18n`).
- Patient-entered data (names, notes, chat) is never translated.

**When:** with the doctor and clinic dashboards (Sprints 12–13), where
staff enter their own profiles in both languages. Existing Arabic seed
names will be moved into the `_ar` columns by that migration.

## Seed data

```bash
cd backend
python -m app.db.seed
```

Refuses to run unless `APP_ENV` is `local` or `test`. Wipes and
re-inserts a fixed, realistic dataset, including one login per role (all
with the password `beautyai-dev-2026`, printed when the script finishes):
`admin@beautyai.example.com` (platform admin),
`dr.amira.hassan@example.com` (doctor),
`yasmin.adel@newlook-zamalek.example.com` (clinic admin), and patients
`nour.mohamed@example.com` / `omar.abdelrahman@example.com` (or their
phone numbers). Also: 3 Cairo/Giza clinics, 3
doctors (2 verified, 1 pending), doctor credentials, clinic-staff
memberships with consultation fees (EGP 400–700), Sunday–Thursday opening
hours per clinic, a pending doctor
application (Dr Mona, with two sample documents in `UPLOAD_DIR` and a
login, so the Sprint 12 review queue isn't empty), 4 procedures with per-clinic pricing, ~27 availability
slots, 2 patients with consents, a normal Egyptian-Arabic intake
conversation, a high-risk conversation with a `safety_events` row, one
confirmed appointment, and one approved knowledge document with 2 chunks
(no embeddings yet — that's Sprint 8).
