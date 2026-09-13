# API Reference

## Status: Sprint 2 complete

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
  `code` is one of `not_found` (404), `conflict` (409), `validation_error`
  (422 domain-level) — plain Pydantic validation errors return FastAPI's
  default 422 body.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Sprint 0 — pings Postgres + Redis |
| GET/POST | `/patients` | `search` filters by name or phone |
| GET/PATCH | `/patients/{id}` | |
| GET/POST | `/doctors` | filters: `specialty`, `is_active`, `verification_status` |
| GET/PATCH | `/doctors/{id}` | |
| GET/POST | `/clinics` | filters: `city`, `is_active` |
| GET/PATCH | `/clinics/{id}` | |
| GET/POST | `/procedures` | filter: `category` |
| GET/PATCH | `/procedures/{id}` | |
| GET/POST | `/availability` | filters: `doctor_id`, `clinic_id`, `is_booked`, `start_from`, `start_to` |
| GET/PATCH | `/availability/{id}` | |
| GET/POST | `/appointments` | filters: `patient_id`, `doctor_id`, `clinic_id`, `status` |
| GET/PATCH | `/appointments/{id}` | |
| GET/POST | `/conversations` | filters: `patient_id`, `status`, `channel` |
| GET/PATCH | `/conversations/{id}` | returns nested `messages` |
| GET/POST | `/conversations/{id}/messages` | raw message storage, no LLM call |
| GET/POST | `/intakes` | filters: `conversation_id`, `patient_id`, `status` |
| GET/PATCH | `/intakes/{id}` | |

## Appointment creation — validation rules

`POST /appointments` performs only deterministic checks, no scheduling
intelligence:

1. `patient_id`, `doctor_id`, `clinic_id` must reference existing rows (404).
2. `procedure_id`, if given, must exist (404).
3. `availability_id`, if given, must exist and not already be booked (409).
   On success, the slot is atomically marked `is_booked=true` in the same
   transaction as the appointment insert.
4. `idempotency_key`, if given and already used by another appointment, is
   rejected (409).
5. Setting `status: cancelled` on an appointment tied to a slot releases
   that slot (`is_booked=false`) again.

No candidate ranking, no auto-selection — that is Sprint 11 (matching)
and Sprint 14 (real booking flow).
