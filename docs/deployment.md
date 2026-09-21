# Deployment

## Status: Sprint 17 — production stack defined and checkable

**Not yet deployed anywhere.** Everything here has been written and
verified locally; no production host, domain, TLS certificate or provider
account exists yet. The gap between "runs on a laptop" and "serving real
patients" is exactly the checklist below.

## The stack

```text
            ┌──────── nginx (TLS, rate limits, static) ────────┐
 internet → │  /api/* → backend (gunicorn + uvicorn workers)   │
            │  /*     → frontend (Next.js)                     │
            └───────────────┬────────────────┬─────────────────┘
                            │                │
                     Postgres 16          Redis 7
                     (+ pgvector)      (rate limits, cache)
                            │
                      uploads volume
                   (verification documents)
```

Plus a **notifier** container that runs
`python -m app.notifications.cli run` every five minutes, sending
reminders, receipts and aftercare messages (docs/notifications.md).

Files: `infra/docker-compose.prod.yml`, `backend/Dockerfile.prod`,
`frontend/Dockerfile.prod`, `infra/nginx/production.conf`.

Both images are multi-stage and run as a non-root user; the compiler
toolchain used to build Python wheels never reaches the runtime image.
Database and Redis ports are not published — only the app network reaches
them.

## Deploying

```bash
cp .env.example .env.production          # then fill it in (see below)
cd infra
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

`migrate` runs `alembic upgrade head` once and must finish before the API
starts; the backend waits on it. Then, from inside the backend container:

```bash
python -m app.scripts.preflight          # refuses to pass on an unsafe config
python -m app.rag.cli ingest ../data/knowledge --approve --reviewer "Dr Name, Dermatologist"
python -m app.scripts.create_admin       # the first platform admin
```

## What must be set before launch

`python -m app.scripts.preflight` checks all of this and exits non-zero
if anything is wrong:

| Setting | Why |
|---|---|
| `APP_ENV=production`, `DEBUG=false` | Turns off the interactive docs and debug output |
| `JWT_SECRET_KEY` | 32+ random characters; anything less lets someone mint admin tokens |
| `CORS_ORIGINS` | The real frontend origin, never `*` (the refresh cookie needs credentials) |
| `PUBLIC_API_URL`, `FRONTEND_URL` | `https://`; payment webhooks and reset links are built from them |
| `AI_PROVIDER=openai` + key and models | The demo provider must never serve patients |
| `PAYMENT_PROVIDER=paymob` + keys | Real payments; the demo gateway is refused |
| `NOTIFICATION_PROVIDER=live` + SMTP / Twilio | Reminders and receipts actually leave |
| `UPLOAD_DIR` | A mounted volume, backed up — verification documents live there |

The seed script refuses to run outside `local`/`test`, so production data
can't be wiped by it.

## Backups and retention

Back up, at least daily:

- **Postgres** — everything: accounts, appointments, payments, messages.
  `pg_dump -Fc` to off-host storage, and *test the restore*.
- **The uploads volume** — doctors' verification documents. Losing these
  means re-verifying every doctor.

Redis holds rate-limit counters only and can be lost safely.

Retention and deletion are described in [`privacy.md`](privacy.md).

## Still to do before real patients

- A host, a domain, and TLS certificates (nginx expects
  `infra/nginx/certs/fullchain.pem` and `privkey.pem`; Let's Encrypt via
  certbot is the obvious route, and the HTTP challenge path is already
  routed).
- Provider accounts and live tests: **Paymob** (one real card payment, one
  wallet payment, a refund), **Twilio** (one SMS, one WhatsApp, with an
  approved WhatsApp template), **SMTP** (deliverability: SPF, DKIM, DMARC).
- Error tracking and uptime monitoring. The app logs structured JSON to
  stdout; nothing collects it yet.
- Database backups actually scheduled and restored once, in anger.
- A staging environment that mirrors production, so releases are rehearsed.
- Load testing: no idea yet how many concurrent chats one worker handles.
- A CI pipeline running `pytest`, `ruff`, `tsc`, `next lint` and
  `python -m app.evaluation.cli run` on every change.
