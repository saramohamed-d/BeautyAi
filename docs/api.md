# API Reference

## Status: Sprint 17 complete

Base path: `/api/v1`. Interactive docs (Swagger UI) at `/docs` whenever the
backend is running.

## Conventions

- **Pagination**: every list endpoint accepts `page` (default 1) and
  `page_size` (default 20, max 100), returns:
  ```json
  {"items": [...], "total": 42, "page": 1, "page_size": 20, "pages": 3}
  ```
- **Errors**: one shape everywhere:
  ```json
  {"error": {"code": "not_found", "message": "Patient '...' not found"}}
  ```
  `code` is one of `unauthorized` (401), `forbidden` (403), `not_found`
  (404), `conflict` (409), `validation_error` (422 domain-level), or a
  more specific code: `slot_unavailable`, `cancellation_window_closed`,
  `invalid_status_transition`, `consent_required`,
  `online_payment_unavailable`, `already_submitted` (all 409),
  `doctor_not_verified` (403), `missing_documents`, `no_opening_hours` (422),
  `doctor_not_at_clinic`, `slot_booked`, `cannot_suspend_self`,
  `payment_not_refundable` (409),
  `payment_provider_error` (502),
  `rate_limited` (429). Plain
  Pydantic validation errors return FastAPI's default 422 body.
- **Authentication**: send `Authorization: Bearer <access_token>`. Who may
  call what is in the permission table in [`security.md`](security.md).
  Asking for a record that isn't yours returns 404.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/admin/overview` | Platform admins: reports and what needs attention. See [`admin.md`](admin.md) |
| GET | `/admin/users` | Platform admins: every login; filters `role`, `status`, `q` |
| PATCH | `/admin/users/{id}` | Suspend or restore a login (ends its sessions) |
| POST | `/admin/payments/{id}/refund` | Refund by hand, with a reason |
| GET | `/admin/notifications` | Platform admins: every message written. See [`notifications.md`](notifications.md) |
| POST | `/admin/notifications/dispatch` | Sends everything due now |
| GET | `/admin/audit-events` | The audit log; filters `action`, `resource_type`, `resource_id`, `actor_id` |
| GET | `/health` | Sprint 0 — pings Postgres + Redis. Public |
| POST | `/auth/register` | Patient sign-up; logs in immediately. Body: `full_name`, `email`, `phone`, `password`, optional `date_of_birth`, `gender`, `city`, `preferred_language` |
| POST | `/auth/register/doctor` | "Join as a Doctor": login + unverified profile. See [`verification.md`](verification.md) |
| POST | `/auth/login` | `{"identifier": email or phone, "password"}` |
| POST | `/auth/refresh` | Uses the refresh cookie; rotates it |
| POST | `/auth/password/forgot` | Sends a reset link; the same answer whether or not the account exists |
| POST | `/auth/password/reset` | `{"token", "password"}`; ends every session. 401 `invalid_token` |
| POST | `/auth/verify/request` | Sends a 6-digit code to your own email or phone |
| POST | `/auth/verify/confirm` | `{"channel", "code"}`; five wrong guesses spends the code |
| GET | `/auth/me/data` | Everything held about you, as JSON (PDPL access). See [`privacy.md`](privacy.md) |
| POST | `/auth/me/delete` | Deletes the account; needs the password |
| POST | `/auth/logout` | Revokes this device's session; 204 |
| GET | `/auth/me` | Current user and patient profile |
| GET/POST | `/patients` | `search` filters by name or phone |
| GET/PATCH | `/patients/{id}` | PATCH also sets the notification channels (`notify_email`, `notify_sms`, `notify_whatsapp`) |
| GET/POST | `/doctors` | filters: `specialty`, `is_active`, `verification_status` |
| GET | `/doctors/applications` | Admins: the verification queue, longest waiting first, with documents |
| GET | `/doctors/search` | Public matching with next slot and price; see "Doctor search" below |
| GET/PATCH | `/doctors/{id}` | |
| GET/POST | `/doctors/{id}/documents` | Doctor (own) or admin. POST is multipart: `document_type` + `file` (PDF/JPEG/PNG/WebP, ≤ `MAX_UPLOAD_MB`) |
| GET | `/doctors/{id}/documents/{doc_id}/file` | Streams the file to its owner or an admin; never a public URL |
| DELETE | `/doctors/{id}/documents/{doc_id}` | Doctor (own) or admin, while not yet verified |
| PATCH | `/doctors/{id}/documents/{doc_id}` | Admins: `{"status": "accepted" \| "rejected", "review_notes"}` |
| POST | `/doctors/{id}/submit` | Doctor: send the application for review (needs a licence and an ID) |
| POST | `/doctors/{id}/verification` | Admins: `{"status": "verified"}` or `{"status": "rejected", "notes": "why"}` (a reason is required) |
| GET/POST | `/clinics` | filters: `city`, `is_active` |
| GET/PATCH | `/clinics/{id}` | |
| GET | `/clinics/{id}/summary` | Clinic admin dashboard figures. See [`clinic-admin.md`](clinic-admin.md) |
| GET/POST | `/clinics/{id}/staff` | The clinic's team; POST a doctor with `doctor_id` |
| PATCH/DELETE | `/clinics/{id}/staff/{staff_id}` | Fee, contact details, deactivate / remove |
| GET/PUT | `/clinics/{id}/hours` | Weekly opening hours (`days`: weekday 0-6, `opens_at`, `closes_at`, `is_closed`) |
| GET/POST | `/clinics/{id}/services` | Per-clinic prices; PATCH/DELETE on `/services/{id}` |
| POST | `/clinics/{id}/slots/generate` | Publishes bookable times from the opening hours (≤ 90 days) |
| DELETE | `/clinics/{id}/slots/{availability_id}` | Removes a free time (409 `slot_booked` otherwise) |
| PUT | `/clinics/{id}/doctors/{doctor_id}/fee` | Admin or the clinic's admin: `{"consultation_fee": 500}` (EGP, or null = confirmed by the clinic) |
| GET/POST | `/procedures` | filter: `category` |
| GET/PATCH | `/procedures/{id}` | |
| GET/POST | `/availability` | filters: `doctor_id`, `clinic_id`, `is_booked`, `start_from`, `start_to`, `available` (bookable now by the caller) |
| POST/DELETE | `/availability/{id}/hold` | Patient holds a slot during payment; see "Holds" below |
| GET/PATCH | `/availability/{id}` | |
| GET/POST | `/appointments` | filters: `patient_id`, `doctor_id`, `clinic_id`, `status` |
| GET/PATCH | `/appointments/{id}` | PATCH: status / notes / cancellation_reason only. Cancelling a paid appointment refunds it |
| POST | `/appointments/{id}/reschedule` | Move to another slot with the same doctor |
| GET/POST | `/conversations` | filters: `patient_id`, `status`, `channel` |
| GET/PATCH | `/conversations/{id}` | returns nested `messages` |
| GET | `/conversations/{id}/messages` | patient (own) or admin |
| POST | `/conversations/{id}/messages` | admins only: raw storage, no screening |
| POST | `/conversations/{id}/chat` | patient AI consultation; see [`agents.md`](agents.md). Returns `sources`, `consultation` (status, missing_fields, data, assessment), and booking options in `assistant_message.extra_data.booking`. 429 `rate_limited` over the hourly limit |
| POST | `/conversations/{id}/booking/reserve` | Patient: hold one of the booking agent's offered options (`availability_id`); 404 if not offered, 409 `slot_unavailable` if taken. Returns hold, slot, doctor, clinic |
| GET | `/payments/quote` | Patient: fee and methods for `availability_id`. See [`payments.md`](payments.md) |
| POST | `/payments/checkout` | Patient: `availability_id`, `method` (`card`/`wallet`/`pay_at_clinic`), `idempotency_key`. Returns `payment`, `checkout_url` (online) or `appointment` (pay at clinic) |
| GET | `/payments` | Patient: own; admin: all, filter `status` (e.g. `needs_refund`) |
| GET | `/payments/{id}` | Owner or admin |
| POST | `/payments/webhooks/{provider}` | Gateway notifications; signature required (401 otherwise) |
| GET | `/knowledge/search` | Public hybrid search of approved articles: `q`, `language`, `limit` |
| GET | `/knowledge/documents` | Public: approved articles; admins: any, filter `status` |
| GET | `/knowledge/documents/{id}` | Public if approved (else 404); admins: any |
| POST | `/knowledge/documents` | Admins: add an article (enters `pending_review`) |
| PATCH | `/knowledge/documents/{id}` | Admins: edit (text change → back to review), approve (`reviewed_by` required), archive |
| GET | `/safety-events` | admins: escalations; filters `requires_human`, `resolved`, `risk_level` |
| PATCH | `/safety-events/{id}` | admins: `resolved`, `notes` |
| GET/POST | `/intakes` | filters: `conversation_id`, `patient_id`, `status` |
| GET/PATCH | `/intakes/{id}` | |

## Booking rules (Sprint 6)

### Booking — `POST /appointments`

1. `patient_id`, `doctor_id`, `clinic_id` (and `procedure_id`, if given)
   must exist (404).
2. With an `availability_id` (the normal case), the slot must belong to
   the same doctor and clinic (422), and must be **bookable**: in the
   future, not booked, and not held by another patient. Otherwise 409
   with code `slot_unavailable`. The appointment's times are always
   copied from the slot; times in the request are ignored.
3. **Concurrency:** the slot row is locked while it's checked and booked,
   so simultaneous requests for one slot get exactly one 201 and 409s for
   the rest, never a 500. A partial unique index ("one non-cancelled
   appointment per slot") backs this up in the database.
4. **Idempotency:** repeating a request with the same `idempotency_key`
   returns the original appointment (also under concurrency). Reusing a
   key for a different patient is a 409.
5. The slot is marked booked, and any hold cleared, in the same transaction.
6. `cancellable_until` is set from the clinic's `cancellation_cutoff_hours`
   (default 24): the patient can cancel or reschedule online until then.
   A later policy change doesn't affect existing bookings.

### Holds — `POST` / `DELETE /availability/{id}/hold` (patients)

Reserves a slot for the calling patient while they pay, for
`SLOT_HOLD_MINUTES` (default 10). Calling again extends it. A patient
holds one slot at a time: a new hold releases their previous one. Others
can't hold or book a held slot (409 `slot_unavailable`), and it's hidden
from their `?available=true` listings; the holder still sees it. Expired
holds simply stop counting; no cleanup job is needed. Booking doesn't
*require* a hold.

### Status changes — `PATCH /appointments/{id}`

Body: `status`, `notes`, and `cancellation_reason` (only with
`status: cancelled`). Other fields are rejected (422): times change only
through rescheduling.

| From | Allowed to |
|---|---|
| `pending` | `confirmed`, `cancelled` |
| `confirmed` | `completed`, `no_show` (only after the start time), `cancelled` |
| `cancelled`, `completed`, `no_show` | nothing (final) |

Anything else is 409 `invalid_status_transition`. Cancelling frees the
slot immediately (bookable again) and records `cancelled_at`,
`cancelled_by_user_id` and `cancellation_reason`. **Patients** can only
cancel, and only until `cancellable_until` (409
`cancellation_window_closed` after that). Staff can cancel any time.

### Rescheduling — `POST /appointments/{id}/reschedule`

Body: `{"availability_id": "<new slot>"}`. Moves an active appointment to
another bookable slot **with the same doctor** (any of their clinics;
422 otherwise). The new slot is booked and the old one freed in one
transaction, with both slots locked in a fixed order so concurrent
reschedules can't deadlock. The appointment returns to `pending` (the
clinic confirms the new time), and `cancellable_until` follows the new
clinic's policy. Patients: same window as cancelling. Clinic admins can
only move appointments into clinics they manage.

### Doctor search — `GET /doctors/search` (public)

Structured matching for the patient app and, from Sprint 10, the Booking
Agent. Verified, active doctors only (unless `verified_only=false`).

| Parameter | Meaning |
|---|---|
| `q` | Text in name or specialty |
| `specialty` | Specialty (partial match) |
| `city` | Practises in this city (membership or slots there); next slot is also limited to that city |
| `procedure_id` | Offers this procedure |
| `max_price` | Cheapest price (for `procedure_id`, or any procedure) at most this |
| `available_before` | Has a bookable slot starting before this time |
| `sort` | `soonest` (default), `rating`, `price` |

Each result: `doctor`, `next_slot` (the soonest slot bookable *by the
caller*), `price_from`, and `clinics` (active clinics where they have
bookable slots). The whole page is built with three queries, however many
doctors it holds.
