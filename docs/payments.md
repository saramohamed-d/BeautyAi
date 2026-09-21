# Payments

## Status: Sprint 11 complete

Patients pay the consultation fee by **card** or **mobile wallet** through
[Paymob](https://paymob.com) (an Egyptian gateway), or choose **pay at
clinic**. Local development and tests use a built-in **demo gateway**
instead, so nothing here needs a Paymob account to run.

InstaPay is **not** offered: we couldn't confirm from Paymob's public
documentation that it's available through the same checkout. The approved
demo design showed it; it can be added later as another method if the
merchant account supports it.

## The rule: no appointment until the money is confirmed

1. **Quote** — `GET /payments/quote?availability_id=…` returns the fee and
   the methods on offer. The fee is the doctor's `consultation_fee` at that
   clinic (`clinic_staff.consultation_fee`, set by the clinic or an admin).
   No fee set → only "pay at clinic" is offered.
2. **Checkout** — `POST /payments/checkout` with `availability_id`,
   `method` and an `idempotency_key`:
   - **Online** (card / wallet): the slot is held for the patient for
     `PAYMENT_WINDOW_MINUTES` (default 15), a `pending` payment is stored,
     and the gateway returns a checkout URL. The patient pays on the
     gateway's own page; we never see card details.
   - **Pay at clinic**: the appointment is booked immediately and the
     payment is recorded as `due_at_clinic`.
3. **Confirmation** — only the gateway's **signed server-to-server
   notification** (webhook) marks a payment `paid`. The appointment is then
   created by the same booking code as everything else (row lock, "one
   active appointment per slot", idempotency key `payment:<id>`), so a paid
   slot can never be double-booked.
4. **Return** — the gateway sends the browser to
   `/payment/return?payment_id=…`. That page only *reads* the payment and
   polls until the webhook has arrived; the browser coming back proves
   nothing and changes nothing.

### When things go wrong

| Situation | What happens |
|---|---|
| Card declined | Payment `failed`; slot stays held until the window ends, so the patient can retry or switch to pay at clinic |
| Patient abandons checkout | Hold expires; payment shows as `expired` (15 min + 2 min grace) |
| Payment succeeds after the slot went to someone else | Automatic full refund; payment `refunded` with reason "The time was no longer available" |
| Amount received ≠ fee | Automatic full refund |
| Refund call fails | Payment `needs_refund`; logged as an error; admins list them with `GET /payments?status=needs_refund` |
| Same webhook delivered twice | Stored once (`payment_events` unique per provider + transaction + outcome); the repeat is ignored |
| Paid appointment cancelled | Full refund (the clinic's cancellation cutoff still decides whether a patient may cancel) |
| Gateway down when starting checkout | 502 `payment_provider_error`; payment `failed`; the patient can retry or pay at clinic |

Every webhook is stored in `payment_events` first, in its own transaction,
as the audit trail.

## Statuses

`pending` → `paid` | `failed` | `expired`; `paid` → `refund_pending` →
`refunded` | `needs_refund`; `due_at_clinic` for pay at clinic. A `failed`
or `expired` payment can still become `paid` if the gateway later confirms
it (e.g. the patient's second attempt on the same checkout page).

## Paymob integration

`app/payments/gateways.py`, `PaymobGateway`:

- **Create intention** — `POST {PAYMOB_BASE_URL}/v1/intention/` with
  header `Authorization: Token <PAYMOB_SECRET_KEY>`; body: `amount` (piastres),
  `currency` "EGP", `payment_methods` (the integration id for the chosen
  method), `items`, `billing_data`, `special_reference` (our payment id),
  `notification_url`, `redirection_url`, `expiration`. The response's
  `client_secret` opens **Unified Checkout** at
  `{PAYMOB_BASE_URL}/unifiedcheckout/?publicKey=<PAYMOB_PUBLIC_KEY>&clientSecret=<client_secret>`;
  `intention_order_id` is stored as `provider_order_id`.
- **Webhook** — `POST /api/v1/payments/webhooks/paymob?hmac=…`. The HMAC is
  SHA-512 over the documented transaction fields concatenated in order,
  keyed with `PAYMOB_HMAC_SECRET`, compared in constant time. Invalid → 401,
  nothing changes. The outcome comes from `success`, `pending` and
  `is_refunded`; `obj.order.id` links it to our payment.
- **Refund** — `POST /api/acceptance/void_refund/refund` with
  `transaction_id` and `amount_cents`.

**Tested against recorded request/response shapes, not a live Paymob
account.** Before launch, run one real card and one wallet payment, a
declined card and a refund in Paymob's test mode, and confirm the webhook
URL is reachable from the internet (`PUBLIC_API_URL`).

Sources:
- Create intention: https://developers.paymob.com/paymob-docs/developers/intention-apis/create-intention
- HMAC for transaction callbacks: https://developers.paymob.com/paymob-docs/developers/webhook-callbacks-and-hmac/hmac/hmac-transaction-callback
- Paymob's official integration notes (checkout URL, refund endpoint): https://skills.lc/PaymobAccept/Paymob-Claude-Integration-Skill/paymobaccept-paymob-claude-integration-skill-skills-paymob-integration-skill-md
- Webhook handling overview: https://hookdeck.com/webhooks/skills/paymob-webhooks

## Demo gateway

`PAYMENT_PROVIDER=demo` (the default locally). Checkout sends the patient
to `/api/v1/payments/demo/checkout/{id}`, a page served by the backend and
clearly marked "DEMO GATEWAY — no real money", with **Pay successfully**
and **Decline payment** buttons. Each button builds a signed event and runs
it through exactly the same webhook handling as Paymob, then redirects to
the frontend's return page. These routes return 404 with any other
provider, and staging/production refuse to start unless
`PAYMENT_PROVIDER=paymob` with all Paymob settings present.

## Configuration

| Variable | Meaning |
|---|---|
| `PAYMENT_PROVIDER` | `demo` (local/test) or `paymob` (required in staging/production) |
| `PAYMENT_WINDOW_MINUTES` | How long the slot is held while the patient pays online (15) |
| `PUBLIC_API_URL` | The backend's public URL; the webhook address given to Paymob |
| `FRONTEND_URL` | Where the patient returns after checkout |
| `PAYMOB_BASE_URL` | `https://accept.paymob.com` |
| `PAYMOB_SECRET_KEY`, `PAYMOB_PUBLIC_KEY`, `PAYMOB_HMAC_SECRET` | From the Paymob dashboard |
| `PAYMOB_CARD_INTEGRATION_ID`, `PAYMOB_WALLET_INTEGRATION_ID` | One per method; a method without an id isn't offered |

## Not done yet

- Clinic payouts / settlement reports and a platform commission (Sprint 14).
- An admin screen for `needs_refund` payments (Sprint 14; the API filter exists).
- ~~Receipts by email/SMS~~ — done in Sprint 15 (`docs/notifications.md`).
- Reconciliation job that asks Paymob about payments still `pending` after the window.
