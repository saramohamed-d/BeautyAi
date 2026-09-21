# Doctor sign-up & verification

## Status: Sprint 12 complete

Implements the spec's rule (section 4): *"A doctor should not
automatically become verified after registration."*

```text
Doctor registers → uploads documents → submits → admin approves / rejects
```

## What being unverified means

A new doctor gets a real login immediately — they must be able to fill in
their profile and upload documents — but no patient-facing presence:

| | Unverified | Verified |
|---|---|---|
| Log in, edit own profile, upload documents | ✅ | ✅ |
| Appears in `/doctors/search` | – | ✅ |
| Slots can be published (`POST /availability`) | 403 `doctor_not_verified` | ✅ |
| Can be booked (`POST /appointments`) | 403 `doctor_not_verified` | ✅ |

The same check (`ensure_can_practise`) also covers a doctor whose
verification is later withdrawn or who is deactivated: existing slots stop
being bookable at once, and the booking agent stops offering them.

`UserStatus.PENDING` is *not* used for this: it blocks login entirely and
is kept for accounts an admin must activate. The gate here is
`doctors.verification_status`.

## The flow

1. **`POST /auth/register/doctor`** — full name, email, phone, password,
   specialty, sub-specialty, licence number, years of experience, degree,
   university, city (spec's "Suggested Fields"). Creates the login and the
   profile (`pending`, `submitted_at = NULL`) and returns a session.
2. **`POST /doctors/{id}/documents`** — one file per call (multipart:
   `document_type` + `file`). Types: medical licence, medical degree,
   national ID, specialty certificate.
3. **`POST /doctors/{id}/submit`** — the doctor sends the application in.
   A medical licence **and** an ID must be on file, otherwise 422
   `missing_documents`; submitting twice is 409 `already_submitted`.
4. **`GET /doctors/applications`** (admin) — the review queue, longest
   waiting first, each with its documents. Admins download a document via
   `GET /doctors/{id}/documents/{doc_id}/file` and can mark each one
   accepted/rejected with `PATCH .../documents/{doc_id}`.
5. **`POST /doctors/{id}/verification`** (admin) — `{"status":
   "verified"}` or `{"status": "rejected", "notes": "why"}`. A rejection
   **must** say why; the reason is stored on the doctor and shown to them.

A rejected doctor fixes the documents and submits again: the application
returns to the queue and the old reason is cleared, so they're never shown
a stale rejection.

Both decisions are written to `audit_events` with the admin's user id
(`doctor.application_submitted`, `doctor.verified`, `doctor.rejected`).

## Uploaded files

`app/storage/files.py`:

- Files are written under `UPLOAD_DIR` (default `backend/var/uploads`,
  gitignored) as `doctors/<doctor id>/<random>.<ext>` — the uploader's
  filename is never used as a path, only kept for display.
- The type is decided by the file's **first bytes**, not by the
  `Content-Type` header or the extension: PDF, JPEG, PNG or WebP only.
  A `.pdf` name on a script is rejected (422).
- The size is capped while streaming (`MAX_UPLOAD_MB`, default 10), so an
  oversized upload is refused rather than buffered.
- Nothing is public: files are returned only by the download endpoint,
  only to the doctor who owns them or a platform admin, always as
  `Content-Disposition: attachment`.
- `stored_path` is relative to `UPLOAD_DIR`, so the storage root can move
  between environments (and later become object storage) without a data
  migration.

## Who may do what

| Action | Doctor (own) | Platform admin | Anyone else |
|---|---|---|---|
| Upload / list / download / delete documents | ✅ | ✅ | 404 |
| Submit the application | ✅ | ✅ | 404 |
| Review the queue, accept/reject documents, approve/reject | – | ✅ | 403 |
| Change `verification_status` on the profile | – | ✅ | 403 |

As everywhere else in the API, asking about a doctor that isn't yours
returns 404 rather than 403, so the API doesn't confirm what exists.

## Frontend

- **`/signup/doctor`** — "Join as a Doctor", linked from the login and
  patient sign-up pages. After signing up the doctor lands on the dashboard.
- **`/doctor`** — the dashboard. It leads with where the application
  stands (not started / under review / verified / not approved, with the
  admin's reason), the document list with upload and delete, and the
  "Submit for Review" button, which stays disabled until the licence and
  ID are uploaded. Once verified it shows upcoming appointments instead.
- Logging in as a doctor lands on `/doctor`.

## Not done yet

- **The admin review screen** (Sprint 14, platform admin dashboard). The
  API above is what it will call; for now approvals are done through the API.
- ~~Email/SMS to the doctor when a decision is made~~ — done in Sprint 15 (`docs/notifications.md`).
- **Licence expiry tracking** and re-verification reminders.
- **Clinic sign-up** and linking a doctor to clinics from the dashboard
  (Sprint 13), including the doctor's own schedule editor.
