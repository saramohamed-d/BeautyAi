# Clinic admin dashboard

## Status: Sprint 13 complete

What a clinic runs day to day, from the spec's clinic capabilities:
its **doctors**, the **services and prices** they offer there, the
**opening hours**, the bookable **times** generated from those hours, and
the **appointments** that result.

Everything is scoped to one clinic and open only to that clinic's admins
and platform admins (`can_manage_clinic`); anyone else gets 403.

## Opening hours → published times

Opening hours are a **template, not a booking rule**. What a patient can
book is still exactly the `availability` rows, so holds, "one active
appointment per slot" and cancellation windows (Sprint 6) are unchanged.

```text
Clinic hours (Sun-Thu 10:00-18:00)  +  slot length (30 min)
        → POST /clinics/{id}/slots/generate for one doctor, over a date range
        → availability rows patients can book
```

- **Generation never disturbs what exists.** Any time that would overlap a
  slot the doctor already has at this clinic is skipped, so running it
  again after adding a day is safe and a booked or held slot is never
  moved or duplicated. The response says how many were created and how
  many were skipped.
- Times in the past are skipped, and so are days the clinic is closed.
- At most **90 days** per run, so a mistyped date can't flood the calendar.
- Only a **verified, active doctor** gets slots (403 `doctor_not_verified`),
  and only one who is **on the clinic's team** (409 `doctor_not_at_clinic`).
- Hours are clinic-local (`CLINIC_TIMEZONE`): the clinic types 10:00 and
  patients in Cairo see 10:00.
- A day with no row is closed, and so is one marked `is_closed` — which
  lets a clinic keep its usual times while closing a day.

Deleting a published time is refused if it's booked (409 `slot_booked`):
cancel the appointment instead, which frees the slot properly and refunds
an online payment (Sprint 11).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/clinics/{id}/summary` | Today, upcoming, awaiting confirmation, doctors, services, free times |
| GET/POST | `/clinics/{id}/staff` | The team. POST a doctor with `doctor_id`, or other staff with `full_name` |
| PATCH/DELETE | `/clinics/{id}/staff/{staff_id}` | Contact details, consultation fee, deactivate; DELETE removes the membership |
| GET/PUT | `/clinics/{id}/hours` | The whole week at once; days left out are closed |
| GET/POST | `/clinics/{id}/services` | Per-clinic prices (`doctor_procedures`) |
| PATCH/DELETE | `/clinics/{id}/services/{service_id}` | Reprice or remove |
| POST | `/clinics/{id}/slots/generate` | `doctor_id`, `date_from`, `date_to`, optional `slot_minutes` |
| DELETE | `/clinics/{id}/slots/{availability_id}` | Removes a free time |

Appointments use the existing `/appointments` endpoints, which already
scope a clinic admin to their own clinics: `GET /appointments?clinic_id=…`
to list, `PATCH /appointments/{id}` to confirm, complete, mark no-show or
cancel.

The session (`/auth/me`, login, refresh) now carries `clinics`: the
clinics this user administers, so the dashboard knows what to offer.

## The consultation fee

`clinic_staff.consultation_fee` is the fee a patient is quoted for that
doctor **at that clinic** (Sprint 11). Setting it on the team screen is
the same value `GET /payments/quote` returns; leaving it empty means the
clinic confirms the price and only "pay at clinic" is offered.

## Frontend

`/clinic`, with six tabs sharing one frame (`components/clinic/clinic-shell.tsx`),
in English and Arabic:

- **Overview** — the day's numbers and today's bookings.
- **Appointments** — filter by status; confirm, complete, mark no-show, cancel.
- **Schedule** — publish times for a doctor over a date range; see and remove free times.
- **Team** — add a doctor, set their consultation fee, remove them.
- **Services** — price a procedure for a doctor, reprice, remove.
- **Hours** — the weekly opening hours and the default appointment length.

An admin managing several clinics picks one in the header; the choice is
remembered in that browser (the backend still checks membership on every
request). Logging in as a clinic admin lands on `/clinic`.

## Not done yet

- **Clinic self sign-up** ("register your clinic"): clinics are created by
  platform admins, who also attach the clinic-admin login.
- **Inviting a doctor by email** who doesn't have a profile yet — today a
  doctor signs up themselves (Sprint 12) and the clinic adds them.
- **Payouts and revenue reports** (Sprint 14).
- **Holidays and one-off closures** beyond the weekly pattern, and per-doctor
  hours that differ from the clinic's.
- **Rescheduling on behalf of a patient** from the dashboard (the API
  supports it; the screen offers cancel only).
