# Notifications and follow-up

## Status: Sprint 15 complete

Reminders, receipts and aftercare over **email, SMS and WhatsApp**, in
the patient's own language.

## What gets sent

| Message | When | To |
|---|---|---|
| Booking confirmed | As soon as an appointment is created | Patient |
| Appointment reminder | `REMINDER_HOURS_BEFORE` (24) before it starts | Patient |
| Aftercare follow-up | `AFTERCARE_HOURS_AFTER` (24) after it ends | Patient |
| Booking cancelled | When it's cancelled, saying if a refund is coming | Patient |
| Payment receipt | When money is actually taken | Patient |
| Verified / not approved | When an admin decides, with the reason | Doctor |

The aftercare message deliberately gives **no medical advice**: it points
the patient back to the clinic that treated them, and offers the AI
consultation for general questions with the usual "not a diagnosis" line.

## How it works

**Every message is a row, written before anything is sent.** Booking an
appointment writes three: the confirmation (due now), the reminder (due
tomorrow) and the follow-up (due the day after). A separate sender
delivers whatever is due:

```bash
python -m app.notifications.cli run       # send everything due (cron, every few minutes)
python -m app.notifications.cli pending   # show what's waiting
```

Platform admins can also press **Send due now** on `/admin/messages`.

Consequences of writing first:

- Nothing is sent inside the request that caused it, so a slow or broken
  provider can never fail a booking or a payment.
- What *will* be sent is inspectable, and cancellable: cancelling an
  appointment marks its unsent reminder and follow-up `cancelled` (they
  aren't deleted — the history stays).
- `dedupe_key` is unique and carries the reason (`reminder:<appointment
  id>:email`), so retries, webhook redeliveries and overlapping sender
  runs can't produce a second message.
- A failed send is retried by the next run up to three times, then left
  as `failed` with the provider's reason, rather than looping forever.

## Channels and preferences

Patients choose their channels in **Profile → Reminders and updates**
(email and SMS on by default, WhatsApp opt-in because it needs an
approved template and a business account). A channel that's turned off,
or that we have no address for, still produces a row with status
`skipped` — "why didn't they get an SMS?" must be answerable.

SMS and WhatsApp use shorter wording than email: an SMS costs money per
segment and is read on a lock screen.

## Providers

`app/notifications/providers.py`, one interface, chosen by
`NOTIFICATION_PROVIDER`:

- **demo** (default locally and in tests) — logs the message; nothing
  leaves the machine, and the whole scheduling path still runs.
- **live** — email over **SMTP** (any mailbox provider, no vendor
  lock-in), SMS and WhatsApp over **Twilio**
  (`POST /2010-04-01/Accounts/{sid}/Messages.json`, form-encoded, basic
  auth; WhatsApp is the same endpoint with both numbers prefixed
  `whatsapp:`).

Staging and production refuse to start on the demo provider, and refuse
`live` without SMTP credentials.

**Twilio is tested against its documented request shape, not a live
account.** Before launch: send one real SMS and one WhatsApp message from
the Twilio console, get the WhatsApp message template approved (outside
a 24-hour window WhatsApp only allows approved templates), and check the
sender runs on the production schedule.

## Configuration

| Variable | Meaning |
|---|---|
| `NOTIFICATION_PROVIDER` | `demo` or `live` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_TLS`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | Email |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SMS_FROM`, `TWILIO_WHATSAPP_FROM` | SMS / WhatsApp |
| `REMINDER_HOURS_BEFORE` | How long before an appointment the reminder goes out (24) |
| `AFTERCARE_HOURS_AFTER` | How long after it the follow-up goes out (24) |

## Not done yet

- **Email and phone verification**, and **password reset**: the delivery
  channel they needed now exists, so these are the next auth items
  (Sprint 17).
- **Per-clinic sender identity** (messages come from the platform).
- **Quiet hours** — a reminder due at 03:00 is sent at 03:00.
- **Delivery receipts**: Twilio's status callbacks aren't consumed, so a
  message Twilio accepts and later fails to deliver still shows as sent.
- **Doctor and clinic preferences**: doctors are told about verification
  decisions on whatever address they registered with.
