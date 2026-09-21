# Security & Privacy

## Status: Sprint 17 — accounts, permissions, rate limiting, password reset and verification

## Authentication

One central login system for all four roles: **patient, doctor, clinic
admin, platform admin**. The AI is not a role; from Sprint 7 it acts
through backend tools on behalf of the logged-in user and inherits that
user's permissions.

| Piece | Choice | Why |
|---|---|---|
| Login | Email **or** phone + password (`POST /auth/login`) | Both are common identifiers in Egypt; either works |
| Passwords | bcrypt, cost 12; 8+ characters, max 72 bytes | bcrypt ignores bytes past 72, so longer passwords are rejected instead of silently truncated (Arabic characters are 2 bytes) |
| Access token | JWT (HS256), 30 minutes, returned in the response body | Kept **in memory only** by the frontend, never in localStorage |
| Refresh token | Random 256-bit value in an **httpOnly, SameSite=Lax** cookie scoped to `/api/v1/auth`; 30 days | Page JavaScript can't read it; restores the session after a reload |
| Refresh storage | Only the SHA-256 hash is stored (`refresh_tokens`) | A database leak doesn't expose live sessions |
| Rotation | Every refresh issues a new token and marks the old one used | A stolen token is only useful until its owner's next refresh |
| Reuse detection | Replaying a used token revokes that whole login session (token family) | Detects theft. A **30-second grace period** tolerates legitimate double use (two tabs reloading at once, retries) |
| Logout | Revokes the token family and clears the cookie | |
| Failed logins | Same message and similar timing whether or not the account exists | Prevents account enumeration (a dummy bcrypt check runs for unknown users) |
| Signing key | `JWT_SECRET_KEY`; the app **refuses to start** in staging/production with the default or a key under 32 characters | A guessable key lets anyone mint admin tokens |
| Cookie `Secure` flag | On in staging/production, off locally (plain http) | |

**Sign-up:** only patients can register themselves (`POST /auth/register`).
Doctors and clinics get their own reviewed sign-up flows in Sprints 12–13.
Platform admins are created from the command line:
`python -m app.scripts.create_admin admin@example.com` (password prompted, never logged).

**Existing profiles aren't claimable.** Registering with the phone or
email of an existing patient profile (for example, a walk-in the clinic
created) returns 409 instead of linking the two. Without phone/email
verification, linking would let anyone take over someone's records by
typing their phone number. Linking becomes possible once verification
exists (Sprint 15).

## Authorization (RBAC)

Enforced in the backend on every endpoint, never only in the frontend.
Role checks use `require_roles` (`app/api/deps.py`); "is this *your*
record" checks are in `app/api/permissions.py`.

**Status codes:** 401 = not logged in or bad token. 403 = your role
can't do this. **404 = not yours**: asking for someone else's patient
record, appointment or conversation returns 404, so the API doesn't
confirm it exists.

| Resource | Anonymous | Patient | Doctor | Clinic admin | Platform admin |
|---|---|---|---|---|---|
| Doctors, clinics, procedures, availability: read | ✅ | ✅ | ✅ | ✅ | ✅ |
| Doctors: create | – | – | – | – | ✅ |
| Doctors: edit | – | – | Own profile, **not** verification/activation | – | ✅ |
| Doctor sign-up (`/auth/register/doctor`) | ✅ | | | | |
| Verification documents: upload / read / delete | – | – | Own (404 for others') | – | ✅ |
| Submit an application | – | – | Own | – | ✅ |
| Approve / reject a doctor, review documents | – | – | – | – | ✅ |
| Clinics: create | – | – | – | – | ✅ |
| Clinics: edit | – | – | – | Own clinics, not activation | ✅ |
| Clinic dashboard: team, services, hours, slot generation | – | – | – | Own clinics | ✅ |
| Procedures: create/edit | – | – | – | – | ✅ |
| Availability: create/edit | – | – | Own slots | Own clinics' slots | ✅ |
| Availability: hold during payment | – | ✅ (one slot at a time) | – | – | – |
| Doctor search | ✅ | ✅ | ✅ | ✅ | ✅ |
| Patients: list / create | – | – | – | – | ✅ |
| Patients: read | – | Self | Patients with an appointment with them | Patients with an appointment at their clinics | ✅ |
| Patients: edit | – | Self | – | – | ✅ |
| Appointments: list / read | – | Own | Own | Their clinics' | ✅ |
| Appointments: create | – | For self only | – | At their clinics | ✅ |
| Appointments: edit | – | Own: **cancel or notes only**, until the clinic's cutoff | Own | Their clinics' | ✅ |
| Appointments: reschedule | – | Own, until the clinic's cutoff | Own | Their clinics', into their clinics | ✅ |
| Payments: quote / checkout | – | For self only | – | – | – |
| Payments: read | – | Own | – | – | ✅ |
| Consultation fee: set | – | – | – | Their clinics | ✅ |
| Payment webhook | Gateway only, verified by signature | | | | |
| Conversations | – | Own; first one requires accepting the AI terms | – | – | ✅ |
| AI chat (`/chat`) | – | Own conversations | – | – | – |
| Reserve a booking-agent option | – | Own conversations, offered options only | – | – | – |
| Raw messages: post | – | – | – | – | ✅ |
| Safety events | – | – | – | – | ✅ |
| Platform reports, user administration, audit log | – | – | – | – | ✅ |
| Refund a payment by hand | – | – | – | – | ✅ |
| Knowledge: read / search approved | ✅ | ✅ | ✅ | ✅ | ✅ |
| Knowledge: drafts, add, edit, approve | – | – | – | – | ✅ (approval needs a named reviewer) |
| Intakes: read | – | Own | – | – | ✅ |
| Intakes: create/edit | – | – | – | – | ✅ (and the AI layer, later) |

Doctors and clinic admins will see consultation summaries through their
dashboards (Sprints 12–13) rather than raw chat access.

Covered by `backend/tests/test_auth_api.py` and `backend/tests/test_permissions.py`.

## AI chat safety (Sprint 7)

Details in [`agents.md`](agents.md). In short: every patient message is
screened by deterministic bilingual rules before any model sees it;
possible emergencies get a fixed message (call 123) and alert a human
without calling the model; the model's structured output can only
suggest specialties from a fixed list; fixed cautions are appended in
code; only message text reaches the provider (`store=False`, hashed user
id); message length and hourly limits cap cost and abuse; and patients
accept a versioned AI disclaimer before their first chat. Patients can't
write assistant/system messages or intakes directly.

## Other measures

- All secrets come from environment variables via `app/core/config.py`;
  `.env` is gitignored.
- CORS is limited to the configured frontend origins (`CORS_ORIGINS`),
  with credentials allowed only because the refresh cookie needs them.
- The seed script refuses to run unless `APP_ENV` is `local` or `test`
  (it wipes every table).

## Uploaded files (Sprint 12)

- Verification documents are written outside the web root under
  `UPLOAD_DIR` with random names, and returned only by an endpoint that
  checks ownership first, always as an attachment.
- The file type is taken from the file's own first bytes (PDF, JPEG, PNG,
  WebP only), never from the filename or the `Content-Type` header, and
  the size is capped while streaming.
- The uploader's filename is sanitised and kept for display only; stored
  paths are checked against the storage root so they can't escape it.
- An unverified doctor has no patient-facing presence at all
  (`ensure_can_practise`). See [`verification.md`](verification.md).

## Notifications (Sprint 15)

- Messages are stored with their rendered text, so what was sent to a
  patient is part of their record and readable only by platform admins.
- Channels are opt-out per patient, and WhatsApp is opt-in.
- Nothing is sent from inside a request; the sender runs separately, so a
  provider can't stall or fail a booking.
  See [`notifications.md`](notifications.md).

## Suspension and the audit trail (Sprint 14)

- Suspending a login revokes its refresh tokens, and its access token is
  rejected on the next request. The 401 message doesn't say the account
  was suspended.
- An admin can't change their own account's status.
- Verification decisions, suspensions and manual refunds are written to
  `audit_events` with the admin's user id and the reason given. The log
  is append-only and readable only by platform admins.
  See [`admin.md`](admin.md).

## Payments (Sprint 11)

- Card details are entered only on the gateway's page; the backend never
  receives or stores them.
- A payment is confirmed only by the gateway's signed webhook (Paymob:
  HMAC-SHA512 with `PAYMOB_HMAC_SECRET`, constant-time comparison). The
  browser returning from checkout changes nothing.
- The amount received is checked against the fee; a mismatch is refunded.
- The demo gateway can't be enabled in staging/production (config check).
  See [`payments.md`](payments.md).

## Password reset and verification (Sprint 17)

- **Reset links and verification codes are stored hashed**, are
  single-use, and asking for a new one revokes the old.
  Links last 30 minutes, codes 15, and a code is spent after five wrong
  guesses.
- **"Forgot password" tells a stranger nothing**: the same answer for a
  known and an unknown address, and nothing is sent to an address with no
  account.
- **Resetting a password revokes every refresh token** on that account,
  so whoever else was signed in is signed out.
- Verifying an email address or phone number sets
  `users.email_verified_at` / `phone_verified_at`. Nothing is gated on it
  yet; it's recorded so that gating can be turned on deliberately.

## Rate limiting (Sprint 17)

Per endpoint group, keyed by IP address, in Redis
(`app/core/rate_limit.py`): 10 logins per 5 minutes, 5 registrations per
hour, 5 password-reset requests per 15 minutes, 5 verification codes per
15 minutes. Over the limit is 429 `rate_limited` with `Retry-After`.

If Redis is unreachable the limiter falls back to counting **in the
process** — weaker with several workers, but a broken cache must not
remove limiting entirely, and it must never lock anyone out. nginx adds a
coarser per-address limit in front (docs/deployment.md), and the AI chat
keeps its own hourly limit per patient.

## Response headers (Sprint 17)

Every response carries `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a restrictive
`Content-Security-Policy` (the API returns JSON: nothing to run, nothing
to embed) and `Permissions-Policy`. Staging and production add HSTS. The
interactive API docs are turned off in production.

## Not done yet

- **Clinical review** of the red-flag rules (see above).
- **Two-factor authentication** for platform and clinic admins.
- **Secret rotation**: keys live in the environment; there's no vault or
  rotation procedure.
- **Automated retention/erasure jobs** — see [`privacy.md`](privacy.md).
- **Penetration testing** and dependency scanning in CI.
- **Clinical review** of the chat's red-flag rules and fixed safety
  messages before launch. Sprint 16 added an evaluation suite that holds
  red-flag recall at 1.00 against a hand-written English/Arabic dataset
  (`docs/evaluation.md`), and fixed six gaps it found — but both the
  rules and the test cases still need a dermatologist's sign-off. One
  rule change (fever plus spreading redness after a procedure is now an
  emergency, not a caution) is a development-team judgement call.
- **Audit log entries** for sign-ins and permission-sensitive actions
  (`audit_events` exists; writing to it is Sprint 14/17). Auth events are
  currently written to the structured application log.
- PII minimization, log redaction, data retention — Sprint 17.

**Legal note:** this project does not, on its own, guarantee compliance
with Egyptian or regional healthcare data protection law (Law 151/2020).
Legal review is required before handling real patient data in production.
