# Platform admin dashboard

## Status: Sprint 14 complete

What the platform team needs to run BeautyAI: who is on it, which doctors
are waiting to be verified, what the money is doing, and a record of what
administrators did. Platform admins only; every other role gets 403.

## What it shows

**Overview** opens with *what needs a human today* — doctor applications
waiting, refunds the gateway refused, unresolved safety escalations and
articles pending review — each linking to where it's handled. Then the
figures: money collected (all time and this month), refunds, people,
clinics, upcoming bookings, and a 14-day bar list of bookings and revenue
per clinic-local day.

**Verification** is the Sprint 12 queue with the decision attached: the
doctor's licence number, when they applied, their documents (downloaded
through the permission-checked endpoint, never a public URL), and
Approve / Reject. A rejection needs a reason, which the doctor sees.

**Payments** lists every payment, defaulting to the *needs refund* pile —
payments where the money was taken but the gateway refused the automatic
refund (Sprint 11). An admin retries the refund, or refunds a paid
booking as a goodwill gesture, with a reason. If the gateway refuses
again the payment stays in the list.

**Users** is every login, filtered by role, status or a search on email /
phone, with suspend and restore.

**Audit log** is the append-only record of administrator decisions,
newest first, filtered by action prefix or resource type.

## The two actions that belong only here

**Suspending a login** sets `users.status = suspended` and revokes that
user's refresh tokens, so an open browser tab can't keep renewing an
access token. A suspended account is refused at login, and its existing
access token stops working on the next request (401, with a message that
doesn't say why — the token is simply not valid any more). An admin
**can't suspend themself** (409 `cannot_suspend_self`): that would lock
the platform out of its own dashboard.

**Refunding by hand** (`POST /admin/payments/{id}/refund`) runs the same
refund path as the automatic ones, so the outcome is the same:
`refunded`, or `needs_refund` if the gateway refuses again. Payments
where no money was taken (pay at clinic, pending, failed) are refused
with 409 `payment_not_refundable`.

Both are written to `audit_events` with the admin's user id and the
reason, alongside the doctor decisions from Sprint 12.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/admin/overview` | Users, doctors, clinics, appointments, payments, "needs attention", 14-day series |
| GET | `/admin/users` | Filters: `role`, `status`, `q` (email or phone) |
| PATCH | `/admin/users/{id}` | `{"status": "suspended" \| "active", "reason": "…"}` |
| POST | `/admin/payments/{id}/refund` | `{"reason": "…"}`; 409 `payment_not_refundable` |
| GET | `/admin/audit-events` | Filters: `action` (prefix), `resource_type`, `resource_id`, `actor_id` |

The dashboard also uses endpoints that already existed: the verification
queue (`GET /doctors/applications`, `POST /doctors/{id}/verification`),
payments (`GET /payments?status=…`), safety events and knowledge review.

## What's audited today

| Action | Written when |
|---|---|
| `doctor.application_submitted` | A doctor sends their application in |
| `doctor.verified` / `doctor.rejected` | An admin decides, with the reason |
| `user.suspended` / `user.active` | An admin suspends or restores a login |
| `payment.refund_requested` | An admin refunds by hand, with the outcome |

Audit rows keep no foreign keys, so an entry survives the record it
describes (see `docs/database.md`).

## Not done yet

- **Changing someone's role**, or creating staff logins from the
  dashboard: clinic-admin and platform-admin logins are still created
  with `app/scripts/create_admin.py` and the seed.
- **Exporting reports** (CSV) and longer date ranges than 14 days.
- **Clinic payouts / settlement**: the platform sees what was collected,
  but there is no commission split or payout run yet.
- **Rate limiting** on admin endpoints and IP capture for audit rows
  (`audit_events.ip_address` exists but isn't filled).
- Safety escalations and knowledge review still use their own Sprint 7/8
  endpoints; the dashboard links to the counts rather than embedding
  those screens.
