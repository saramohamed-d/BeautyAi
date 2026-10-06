# Running BeautyAI locally (WSL, without Docker)

These steps run everything directly in WSL from the VS Code terminal.
All downloads stay on the D: drive.

| Part | Where it runs |
|---|---|
| Database | PostgreSQL 16 already installed in WSL, port `5432` |
| AI chat | Ollama already installed, port `11434`, model `qwen2.5:3b` |
| Backend (FastAPI) | http://localhost:8002 (port 8000 is used by another project) |
| Frontend (Next.js) | http://localhost:3000 |

Redis is optional. Without it, the rate limiter counts in memory.

---

## One-time setup

### 1. Create the database

Needs your sudo password. Run once:

```bash
sudo -u postgres psql \
  -c "CREATE ROLE beautyai LOGIN PASSWORD 'beautyai' CREATEDB;" \
  -c "CREATE DATABASE beautyai OWNER beautyai;" \
  -c "\c beautyai" \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

This creates a `beautyai` user and database, and enables pgvector, which the
knowledge search needs. Nothing else is changed.

### 2. Install the backend packages

Already done (`backend/.venv`, about 141 MB). To redo it, keeping pip's cache on D:, run:

```bash
cd /mnt/d/saradoha/ba/BeautyAi/backend
python3 -m venv .venv
PIP_CACHE_DIR=/mnt/d/saradoha/ba/_downloads/pip-cache .venv/bin/pip install -r requirements.txt
```

### 3. Create the backend settings file

The backend reads `.env` from the folder it runs in, so put it in `backend/`:

```bash
cd /mnt/d/saradoha/ba/BeautyAi/backend
cp ../.env.example .env
```

Then edit these two lines in `backend/.env` so the website on port 3000 can
call the backend on port 8002:

```
CORS_ORIGINS=["http://localhost:3000"]
PUBLIC_API_URL=http://localhost:8002
```

(`AI_PROVIDER=ollama` and `OLLAMA_MODEL=qwen2.5:3b` are already set.)

### 4. Create the tables and the sample data

```bash
cd /mnt/d/saradoha/ba/BeautyAi/backend
source .venv/bin/activate
alembic upgrade head
python -m app.db.seed
```

### 5. Make sure the AI model is there

```bash
ollama list            # qwen2.5:3b should be listed
```

If it's missing, run `ollama pull qwen2.5:3b` (about 1.9 GB; check where Ollama stores models first).

---

## Every time you want to run it

Open **two terminals** in VS Code (the `+` button in the terminal panel).

**Terminal 1: backend**

```bash
cd /mnt/d/saradoha/ba/BeautyAi/backend
source .venv/bin/activate
WATCHFILES_FORCE_POLLING=true uvicorn app.main:app --reload --port 8002
```

`WATCHFILES_FORCE_POLLING=true` does the same job for the backend: it reloads when you edit Python files.

Check it works: http://localhost:8002/api/v1/health

**Terminal 2: frontend**

```bash
cd /mnt/d/saradoha/ba/BeautyAi/frontend
NEXT_PUBLIC_API_URL=http://localhost:8002 WATCHPACK_POLLING=true npm run dev
```

`WATCHPACK_POLLING=true` makes the page reload when you edit files. Without
it, changes to files on the D: drive aren't detected under WSL.

Open **http://localhost:3000**

To stop either one, press `Ctrl + C` in its terminal.

---

## Logins for testing

All use the password **`beautyai-dev-2026`**.

| Role | Email | What you should see |
|---|---|---|
| Patient | `nour.mohamed@example.com` | Home, doctors, AI chat, my appointments |
| Patient | `omar.abdelrahman@example.com` | Same as above |
| Doctor | `dr.amira.hassan@example.com` | Only their own dashboard and profile |
| Clinic admin | `yasmin.adel@newlook-zamalek.example.com` | Clinic dashboard, appointments, team |
| Platform admin | `admin@beautyai.example.com` | Admin dashboard, verification, payments, users |

## What to try

1. **Patient:** open *AI Consultation*, tick the box, and describe a skin
   problem. Each reply takes about 20 seconds; the chat shows a seconds counter
   while it waits.
2. **Patient:** open *Doctors*, filter by specialty or city, and press *Book*.
3. **Doctor:** log in, then press *Change avatar* and pick a picture. Try opening
   http://localhost:3000/doctors; you are sent back to your dashboard.
4. **Admin:** open *Verification* and approve or reject a doctor.
5. Switch the language (العربية) at the top to check the Arabic layout.

## Running the backend tests

```bash
cd /mnt/d/saradoha/ba/BeautyAi/backend
source .venv/bin/activate
APP_ENV=test pytest -v
```

The tests use the offline demo AI, so Ollama isn't needed for them
(356 tests, about 3.5 minutes).

> **The tests write into the same `beautyai` database the app uses**, so
> afterwards the app shows "Test Doctor" entries. Reset it to the clean
> sample data with:
>
> ```bash
> sudo -u postgres psql -c "DROP DATABASE beautyai WITH (FORCE);" \
>   -c "CREATE DATABASE beautyai OWNER beautyai;" -c "\c beautyai" \
>   -c "CREATE EXTENSION IF NOT EXISTS vector;"
> alembic upgrade head && python -m app.db.seed
> ```

---

## Problems

| Problem | Fix |
|---|---|
| `password authentication failed for user "beautyai"` | Step 1 hasn't been run yet. |
| `extension "vector" is not available` | Run the `CREATE EXTENSION` line from step 1 as `postgres`. |
| Website loads but shows no doctors / errors | Backend isn't running on 8002, or `NEXT_PUBLIC_API_URL` wasn't set when starting the frontend. |
| Login works but you're logged out on reload | `CORS_ORIGINS` in `backend/.env` must contain `http://localhost:3000`. |
| Chat says it couldn't answer | Check Ollama: `curl http://localhost:11434/api/tags`. Start it with `ollama serve`. |
| First chat reply takes ~40 s | The model is loading into memory. Later replies take about 7–20 s. |
| Chat is very slow | Normal for local AI on a laptop. `qwen2.5:3b` takes about 20 s per reply, `qwen2.5:7b` about 1 min. Change `OLLAMA_MODEL` in `backend/.env`. |
| `Address already in use` | Something else is using the port. Pick another one (for example `--port 8003`) and use the same number in `NEXT_PUBLIC_API_URL`. |
