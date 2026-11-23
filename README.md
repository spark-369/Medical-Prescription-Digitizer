# Medical Prescription Digitizer

A production-style, local-first prescription digitization platform. Upload a
prescription image and a Celery worker runs local vision inference
(Ollama · **Qwen3-VL-2B-Instruct** GGUF Q4_K_M) with **grammar-constrained
structured output**, persisting patient details and medications. The browser
follows progress live over **Server-Sent Events**, and three AI layers build on
the extracted data: **AI insights** (summary, interaction check, daily
schedule), a **grounded AI assistant** (structured chat), and **AI analytics
reports** over the prescription history.

> **Medical disclaimer** — all AI output in this project (extractions,
> summaries, interaction findings, schedules, assistant replies and reports)
> is *informational only*. It is not a diagnosis and never a substitute for a
> pharmacist or physician.

---

## Table of contents

1. [Architecture](#architecture)
2. [Feature overview](#feature-overview)
3. [Tech stack](#tech-stack)
4. [Project structure](#project-structure)
5. [Quick start (Docker)](#quick-start-docker)
6. [Local development](#local-development)
7. [Configuration reference](#configuration-reference)
8. [Authentication & token flow](#authentication--token-flow)
9. [AI pipelines](#ai-pipelines)
10. [API reference](#api-reference)
11. [Data model](#data-model)
12. [Testing & quality](#testing--quality)
13. [Security notes](#security-notes)
14. [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌────────────────────────────────────┐          ┌────────────────────────────────────────────┐
│  Next.js 16 · App Router           │          │  FastAPI (REST + SSE)                      │
│                                    │          │                                            │
│  Auth.js v5 (JWT sessions)         │  Bearer  │  /auth      register·login·refresh·logout  │
│  proxy.ts route protection         ├─────────►│  /prescriptions  upload·CRUD·search·SSE    │
│  Server Components + Actions       │  http    │  /prescriptions/{id}/insights              │
│  Tailwind v4 + shadcn/ui           │          │  /assistant/chat  structured chat replies  │
│  React Hook Form + Zod             │          │  /reports       AI analytics (per user)    │
│                                    │          │  Redis JWT blacklist + rotation            │
└───────────────┬────────────────────┘          └──────────────┬───────────────┬─────────────┘
                │                                              │               │
                │                                       enqueue│        SQL (asyncpg)
                │                                       (Redis)│               │
        ┌───────▼──────────────────────────────────┐    ┌──────▼───────┐  ┌────▼─────────┐
        │  Celery workers                          │    │ Redis pub/sub│  │ PostgreSQL   │
        │  1. prescriptions.process                │◄───┤ progress events│ │ users        │
        │     vision OCR → structured extraction   │    └──────────────┘  │ prescriptions│
        │  2. prescriptions.generate_insights      │                      │ items        │
        │     summary · interactions · schedule    │                      │ ai_reports   │
        │  3. reports.generate_report              │                      └──────────────┘
        │     history analytics → narrative report │
        └───────────────┬──────────────────────────┘
                        │  /api/chat  ·  format = JSON schema (grammar-constrained)
                ┌───────▼──────────────────────────┐
                │  Ollama · Qwen3-VL-2B (Q4_K_M)   │
                └──────────────────────────────────┘
```

## Feature overview

| Area | What you get |
|------|--------------|
| **Digitization** | Multipart image upload → two-pass AI extraction (transcription → structured JSON) → patient, age, doctor, date, medications (name/dosage/frequency/duration/instructions), notes, confidence. Live SSE progress; reprocess; delete. |
| **AI insights** | Per-prescription, auto-generated on first view: patient-friendly summary + key points, drug-interaction safety check (severity-graded findings, overall risk level), and a daily medication schedule. Regenerable. |
| **AI assistant** | Streaming-style chat page with a per-prescription grounding selector, quick prompts, conversation history, and **structured JSON replies** (`answer` + `key_points` + suggested `follow_ups` chips) — clean output, no markdown noise. |
| **AI reports** | One-click analytics report over *your* prescription history: totals, completion rates, top prescribed medications, highlights and actionable recommendations. Persisted per user, deletable. |
| **Prescription library** | Paginated list with status filter pills, server-side search (patient/doctor/filename), relative timestamps, empty states. |
| **Production UI** | Sidebar app shell with mobile drawer, dark/light theme, split-screen auth, loading skeletons, error boundary, not-found states, delete confirmations, toasts. |
| **Accounts & RBAC** | JWT auth with rotating refresh tokens and Redis revocation; roles (`admin`, `doctor`, `staff`); first registered account becomes admin; admin user management. |

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 16 (App Router, Turbopack), React 19, TypeScript, Tailwind CSS v4, shadcn/ui + Radix UI, React Hook Form + Zod, Auth.js v5 (`next-auth` beta), `next-themes` |
| Auth (frontend) | JWT session strategy, credentials provider → FastAPI, `proxy.ts` route protection (Next 16 renamed `middleware.ts`), proactive access-token refresh, httpOnly refresh cookie |
| Auth (backend) | `python-jose[cryptography]`, `passlib[bcrypt]`, Redis jti blacklist, single-use refresh-token rotation with reuse detection |
| Backend | Python 3.11+, FastAPI + Uvicorn, Pydantic v2, SQLAlchemy 2 (async `asyncpg` for API, sync `psycopg` for workers), Alembic |
| Async tasks | Celery (Redis broker + result backend), per-task time limits |
| AI inference | Ollama `/api/chat` with `format` = Pydantic `model_json_schema()` (grammar-constrained JSON); model `hf.co/Qwen/Qwen3-VL-2B-Instruct-GGUF:Q4_K_M` |
| Realtime | Server-Sent Events (prescription processing) with heartbeats; Redis pub/sub progress events |
| Data | PostgreSQL; local filesystem uploads (`./uploads`, CWD-anchored) |
| Testing | pytest + pytest-asyncio (hermetic: SQLite + fakeredis + Celery eager mode), ruff; ESLint + `tsc --noEmit` on the frontend |

---

## Project structure

```
v1/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py                 # DB/Redis/current-user dependencies, RBAC
│   │   │   └── routes/
│   │   │       ├── assistant.py        # POST /assistant/chat (structured replies)
│   │   │       ├── auth.py             # register · login · refresh · logout · me
│   │   │       ├── health.py           # /health · /health/detailed
│   │   │       ├── prescriptions.py    # upload · CRUD · search · stats · SSE · insights
│   │   │       ├── reports.py          # AI analytics reports (per user)
│   │   │       └── users.py            # admin user management
│   │   ├── core/                       # config · errors · logging · redis · security
│   │   ├── db/                         # async engine (API) + sync engine (workers)
│   │   ├── models/                     # user · prescription · prescription_item · ai_report
│   │   ├── schemas/                    # auth · assistant · insights · prescription · report
│   │   ├── services/
│   │   │   ├── chat.py                 # assistant: structured JSON replies
│   │   │   ├── files.py                # validation + storage (CWD-anchored)
│   │   │   ├── inference.py            # two-pass vision extraction
│   │   │   ├── insights.py             # summary · interactions · schedule
│   │   │   ├── ollama.py               # shared Ollama client (chat + JSON schemas)
│   │   │   ├── prescription_service.py # persistence, scoping, stats
│   │   │   ├── report_service.py       # SQL aggregation + report generation
│   │   │   └── user_service.py
│   │   ├── workers/                    # celery app + 3 tasks
│   │   └── main.py
│   ├── alembic/versions/               # 0001_initial · 0002_ai_insights · 0003_ai_reports
│   ├── scripts/create_admin.py
│   ├── tests/                          # 62 hermetic tests
│   └── pyproject.toml
├── frontend/
│   ├── app/
│   │   ├── (auth)/                     # login · register (split-screen layout)
│   │   ├── (app)/                      # dashboard · prescriptions(+[id]) · assistant · reports · users
│   │   │   └── loading.tsx / error.tsx # skeletons + error boundary
│   │   └── api/
│   │       ├── assistant/chat/route.ts # token-hiding chat proxy
│   │       ├── auth/[...nextauth]/     # Auth.js handlers
│   │       └── files/[id]/route.ts     # authenticated image proxy
│   ├── actions/                        # server actions (auth · prescriptions · reports)
│   ├── components/                     # ui/* (shadcn) + app components
│   ├── lib/                            # api client · zod schemas · token refresh · utils
│   ├── auth.ts · auth.config.ts · proxy.ts
│   └── types/next-auth.d.ts
├── docker-compose.yml · Makefile · .github/workflows/ci.yml
└── README.md
```

## Quick start (Docker)

```bash
cp .env.example .env                 # then set SECRET_KEY and AUTH_SECRET
make up                              # postgres · redis · ollama · backend · worker · frontend
docker compose exec ollama ollama pull hf.co/Qwen/Qwen3-VL-2B-Instruct-GGUF:Q4_K_M
docker compose exec backend alembic upgrade head   # or rely on CREATE_ALL_TABLES=true
open http://localhost:3000           # register — the first account becomes admin
```

## Local development

Prerequisites: PostgreSQL, Redis, Ollama with the model pulled, Python 3.11+, Node 20+.

```bash
# backend (terminal 1 + 2)
cd backend
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head                 # first time; CREATE_ALL_TABLES=true also works
uvicorn app.main:app --reload --port 8000
celery -A app.workers.celery_app worker --loglevel=INFO --pool=solo

# frontend (terminal 3)
cd ../frontend
npm install
cp .env.example .env.local
npm run dev                          # http://localhost:3000
```

Bootstrap an admin manually:

```bash
make seed-admin ADMIN_EMAIL=admin@clinic.dev ADMIN_PASSWORD=adminpass123
```

Useful Makefile targets: `up` / `down` / `logs` (compose), `test`, `lint-backend`,
`lint-frontend`, `migrate`, `revision REVISION_MSG="..."`, `pull-model MODEL=...`,
`seed-admin`.

## Configuration reference

### backend/.env

| Variable | Default | Notes |
|----------|---------|-------|
| `ENVIRONMENT` / `DEBUG` / `LOG_LEVEL` | `dev` / `true` / `INFO` | `DEBUG=true` → refresh cookie without `Secure` |
| `SECRET_KEY` | — | **Change it.** Signs all JWTs (`openssl rand -hex 32`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | `30` / `7` | Refresh tokens rotate single-use |
| `DATABASE_URL` | `postgresql+asyncpg://…` | Async driver for the API |
| `DATABASE_URL_SYNC` | `postgresql+psycopg://…` | Sync driver for Celery tasks |
| `CREATE_ALL_TABLES` | `false` | Dev convenience; prefer Alembic |
| `REDIS_URL` / `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | db 0 / 1 / 2 | Blacklist + SSE pub/sub, broker, results |
| `UPLOAD_DIR` | `./uploads` | **Relative paths anchor to `backend/`** so API, worker and CLI agree regardless of CWD; absolute paths used as-is |
| `MIN_UPLOAD_SIZE_KB` | `10` | Minimum accepted upload size |
| `MAX_UPLOAD_SIZE_MB` | `10` | Accepted files are **strictly smaller**; `0` disables the cap |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | `http://localhost:11434` / Qwen3-VL tag | |
| `OLLAMA_TIMEOUT_SECONDS` / `OLLAMA_TEMPERATURE` / `OLLAMA_NUM_CTX` | `240` / `0.1` / `4096` | Context size drives the vision token budget |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON list |

### frontend/.env.local

| Variable | Notes |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | FastAPI URL reachable from the **browser** (SSE EventSource) |
| `API_URL_INTERNAL` | FastAPI URL reachable from the **Next.js server** (server components/actions) |
| `AUTH_SECRET` | **Change it.** Encrypts the Auth.js session cookie |
| `AUTH_TRUST_HOST` | `true` for local/docker dev |

## Authentication & token flow

1. `POST /api/v1/auth/login` (OAuth2 password form) → `{access_token, refresh_token}`
   plus an **httpOnly** `mpd.refresh_token` cookie.
2. The Next.js credentials provider performs that login server-side and stores the
   token pair inside the **encrypted Auth.js JWT session cookie** (also httpOnly).
   Every backend call from the server attaches `Authorization: Bearer <access>`.
3. The Auth.js `jwt` callback refreshes the access token ~60 s before expiry via
   `POST /auth/refresh`; FastAPI **rotates** refresh tokens and blacklists the
   used `jti` in Redis — a replayed refresh token is rejected.
4. Logout blacklists both tokens and clears the cookie — revocation is immediate.
5. `proxy.ts` protects `/dashboard`, `/prescriptions`, `/assistant`, `/reports`
   and `/users` at the edge and bounces authenticated users away from auth pages.
6. SSE endpoints additionally accept `?access_token=` because `EventSource`
   cannot set headers.

## AI pipelines

All AI calls go through one shared Ollama client (`app/services/ollama.py`) that
enforces **JSON-schema `format` constraints** with every key marked required —
the guard that stops small models from returning early with nulls — plus
exact-count list constraints (`minItems`/`maxItems`) and Celery time limits as
backstops.

### 1. Extraction — `prescriptions.process` (two-pass)

Small vision models are unreliable at emitting JSON straight from an image, so:

1. **Transcription** — the vision model transcribes the image line by line
   (plain text, `temperature=0`).
2. **Structured parse** — the transcription is converted into
   `PrescriptionExtraction` under the JSON schema (all keys required, nullable
   values) and persisted with the items.

Progress (5 → 35 → 80 → 100 %) is published on Redis pub/sub and streamed to
the browser via `GET /prescriptions/{id}/events` (heartbeats every 15 s).

### 2. AI insights — `prescriptions.generate_insights`

Triggered automatically the first time a completed prescription is opened
(and re-runnable). Three focused, grammar-constrained calls over the
*extracted data*:

| Pass | Output |
|------|--------|
| Patient-friendly summary | `summary` + `key_points` |
| Interaction check | overall `risk_level` + graded `findings` (severity / description / recommendation) |
| Daily schedule | one entry per medication with 24 h `times`, `days`, instructions |

The schedule grammar is pinned to **exactly one entry per medication** and a
deterministic normalizer harvests stray fields — small-model drift is cleaned
before persistence. The UI polls while `status=pending`; failures are retryable.

### 3. AI assistant — `POST /assistant/chat`

Chat replies are **structured JSON** (`answer`, `key_points`, `follow_ups`) —
never raw markdown. When a prescription is selected the system prompt is
grounded in its extracted data; the last 10 conversation turns are forwarded.
The access token never reaches the browser: a Next.js route proxy attaches it
server-side.

### 4. AI reports — `reports.generate_report`

Aggregation is plain SQL (deterministic); the model only narrates the numbers:
totals, status breakdown, top prescribed medications, distinct doctors and the
observed period become `headline / overview / highlights / recommendations`.
Reports are stored per user in `ai_reports` (`pending → ready/failed`) and
listed newest-first.

---

## API reference

Interactive docs: **http://localhost:8000/docs** (Swagger) and `/redoc`.
All routes are prefixed with `/api/v1`.

### Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | — | Register (201). First account becomes `admin` |
| POST | `/auth/login` | — | OAuth2 password form → tokens + refresh cookie |
| POST | `/auth/refresh` | cookie/body | Rotate tokens; old refresh jti blacklisted |
| POST | `/auth/logout` | Bearer | Blacklist tokens, clear cookie |
| GET | `/auth/me` | Bearer | Current user |

### Users (admin only)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/users` | List all users |
| POST | `/users` | Create a user with a specific role |

### Prescriptions

| Method | Path | Description |
|--------|------|-------------|
| POST | `/prescriptions` | Upload image (multipart) → enqueue processing. Size window: `MIN_UPLOAD_SIZE_KB ≤ size < MAX_UPLOAD_SIZE_MB` |
| GET | `/prescriptions` | Paginated list. Query: `page`, `page_size`, `status`, `search` (matches patient, doctor, filename). Owner-scoped; admin sees all |
| GET | `/prescriptions/stats` | Totals, status breakdown, 5 most recent |
| GET | `/prescriptions/{id}` | Detail incl. items + AI insight fields |
| GET | `/prescriptions/{id}/file` | Original image (authenticated stream) |
| GET | `/prescriptions/{id}/events` | **SSE** progress stream (`?access_token=` fallback) |
| POST | `/prescriptions/{id}/reprocess` | Re-run extraction (409 while active) |
| POST | `/prescriptions/{id}/insights` | Queue AI insights (202; 409 unless completed) |
| DELETE | `/prescriptions/{id}` | Delete row + stored file (204) |

### AI assistant

| Method | Path | Description |
|--------|------|-------------|
| POST | `/assistant/chat` | Body: `{message, prescription_id?, history?}` → structured reply `{answer, key_points[], follow_ups[]}`. Clean JSON — no markdown |

### AI reports

| Method | Path | Description |
|--------|------|-------------|
| GET | `/reports` | Own reports, newest first (max 20) |
| POST | `/reports/generate` | Create pending report + enqueue task (202) |
| DELETE | `/reports/{id}` | Delete own report (204) |

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness + app metadata |
| GET | `/health/detailed` | Component checks: database, redis, ollama |

## Data model

```
users
├── id (uuid, pk) · email (unique) · hashed_password · full_name
├── role (admin | doctor | staff) · is_active · created_at · updated_at
├── 1─N prescriptions (ON DELETE CASCADE)
└── 1─N ai_reports   (ON DELETE CASCADE)

prescriptions
├── owner_id → users.id · original_filename · stored_path · mime_type
├── file_size · checksum (sha256)
├── status (uploaded | queued | processing | completed | failed) · error
├── raw_output · confidence · model_name
├── patient_name · patient_age · doctor_name · prescribed_date · notes
├── processing_started_at · completed_at
├── ai_insights (JSON) · ai_insights_status (pending|ready|failed)
│   ai_insights_model · ai_insights_generated_at
└── 1─N prescription_items (ON DELETE CASCADE)
    └── medication · dosage · frequency · duration · instructions

ai_reports
├── user_id → users.id · status (pending | ready | failed)
├── content (JSON: headline · overview · highlights[] · recommendations[])
└── model · error · created_at · updated_at
```

## Testing & quality

```bash
make test              # backend: 62 hermetic tests — no external services needed
make lint-backend      # ruff
cd frontend && npm run typecheck && npm run lint
```

The backend suite substitutes SQLite (aiosqlite + sqlite3) for PostgreSQL,
`fakeredis` for Redis, runs Celery in **eager mode**, and mocks the Ollama
calls with deterministic fixtures — so `pytest` runs anywhere in seconds.
Covered areas: auth (rotation/reuse/revocation), RBAC, upload validation
(type/size window), owner scoping, the extraction pipeline (incl. failure and
broker-outage paths), insight generation/normalization/failure retry, the
assistant contract, reports aggregation/isolation/failure, and SSE snapshots.

## Security notes

* **Secrets**: `SECRET_KEY` and `AUTH_SECRET` must be replaced in any shared
  environment.
* **Open registration**: registration is open for development convenience and
  the first account becomes admin. Add an invite/approval flow before real
  deployment.
* **AI output is not medical advice**: interaction findings from a 2B local
  model are plausible but not clinically reliable. Every AI surface displays a
  disclaimer; treat outputs as drafts for professional review.
* **Local-first inference**: images and text are sent only to your own Ollama
  instance — no third-party AI APIs.
* **Uploads**: type + size validated; stored under UUID names with SHA-256
  checksums; served only through the authenticated file endpoint.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `502 inference_failed` on upload, worker log shows connection error | Ollama is down or the model isn't pulled: `ollama pull hf.co/Qwen/Qwen3-VL-2B-Instruct-GGUF:Q4_K_M` |
| `relation "users" already exists` during `alembic upgrade head` | The schema was created via `CREATE_ALL_TABLES` — adopt it: `alembic stamp 0001_initial` then `alembic upgrade head` |
| Worker says `Stored file is missing` | Processes were started from different working directories with a relative `UPLOAD_DIR`. The app anchors relative paths to `backend/` — restart both processes on current code |
| Uploads rejected with `Task queue unavailable` | The Celery worker isn't running or Redis broker is down |
| Insight/report stuck in `pending` | A worker was hard-killed mid-run. Re-trigger the endpoint — it re-enqueues (idempotent, last write wins) |
| `next dev` starts but never serves / hangs | Stale `.next` (e.g. after running `next build`). `rm -rf frontend/.next` and restart, or use `npm run build && npm start` |
| fakeredis/redis errors in tests | `redis` is pinned `>=6.1,<7` on purpose: Celery needs ≥ 6.1 and fakeredis introspection breaks on 8.x |
| Frontend shows old behavior after code changes | Ensure you're on the dev server you started (`next dev`), not a leftover `next start` production server of an older build |
| SSE shows nothing | Confirm `NEXT_PUBLIC_API_URL` points at the API from the browser and that the stream was opened while the prescription was still active (completed prescriptions emit only a snapshot) |

## Limitations (development scope)

* Uploads are stored on the local filesystem; no S3/object storage layer yet.
* One vision model at a time (single `OLLAMA_MODEL`); quality depends on image
  legibility and model size — prompts are isolated in
  `backend/app/services/inference.py` / `insights.py` for easy upgrades.
* The assistant keeps conversation history client-side (last 10 turns); there
  is no persisted chat thread yet.
* Reports are per-user and cover the full history; no date-range filters yet.
