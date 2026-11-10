# Long Video Session Planner

Splits one long YouTube video into daily study sessions. Each session has dates, timestamps, chapter breaks, "Open at hh:mm:ss" links and done-ticks. Users have accounts, so plans and progress are saved on the server and follow them across devices.

## Architecture (3 tiers)

```
 Browser                      FastAPI (Python)                         Database
 frontend/                    backend/app/                             SQLite (local default)
 index.html, app.js,   --->   api/v1/       HTTP layer (thin)    --->  or PostgreSQL
 styles.css            /api   services/     business logic             via DATABASE_URL
                       /v1    repositories/ data access
                              models/       SQLAlchemy tables
                              migrations/   Alembic schema versions
```

| Tier | Folder | Responsibility |
|---|---|---|
| Presentation | `frontend/` | Login and signup screens, plan form (autosaved), schedule rendering, reading the video length from the YouTube player when the server has no API key. No build step. |
| Application | `backend/app/` | REST API under `/api/v1`, auth (Argon2 password hashing, server-side sessions in an httpOnly cookie), scheduling logic, YouTube Data API lookups (the key stays on the server). |
| Data | DB via `DATABASE_URL` | Tables `users`, `sessions`, `plans`, `plan_progress`. Schema managed by Alembic and applied automatically on startup. |

Locally, FastAPI also serves `frontend/` so a single process runs everything. In production, nginx can serve `frontend/` and proxy `/api` to the app (`SERVE_FRONTEND=false`).

### Backend layout

```
backend/
├── app/
│   ├── main.py            # App factory: middleware, exception handlers, routers, static frontend
│   ├── config.py          # Settings from env / .env
│   ├── database.py        # Database session setup
│   ├── dependencies.py    # Shared dependencies (DB session, current user, services)
│   ├── exceptions.py      # Domain exceptions + HTTP handlers
│   ├── middleware.py      # CSRF guard, security headers (CSP), request logging
│   ├── api/
│   │   ├── router.py      # Root router (/api)
│   │   └── v1/            # router.py, auth.py, plans.py, youtube.py, meta.py (health, config)
│   ├── models/            # base.py, user.py (User, AuthSession), plan.py (Plan, PlanProgress)
│   ├── schemas/           # Pydantic request/response models
│   ├── services/          # auth_service, plan_service, schedule_service (pure), youtube_service
│   ├── repositories/      # base.py (generic), user_repo.py, plan_repo.py
│   └── core/              # security.py (hashing, tokens, rate limit), logging.py (JSON logs)
├── migrations/versions/   # Alembic migrations
├── tests/                 # pytest: unit (schedule) + API (auth, plans, youtube, meta)
├── pyproject.toml
├── alembic.ini
└── .env.example
```

Requests flow one way: `api/v1/*` → `services/*` → `repositories/*` → `models/*`. Services raise errors from `exceptions.py` and never import FastAPI. Handlers in one place turn those errors into HTTP status codes.

## Run locally

Requires Python 3.12 or newer. Nothing else is needed: the database is a SQLite file created automatically.

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env          # optional, every setting has a default
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 and create an account.

- API docs (Swagger): http://localhost:8000/api/docs
- Health check: http://localhost:8000/api/v1/health
- Data lives in `backend/data/planner.db`. Delete it to start fresh.
- For readable local logs, set `LOG_JSON=false` in `.env`.

### Tests

```bash
cd backend
.venv/bin/python -m pytest
```

54 tests cover scheduling (using the real chapter list of the AWS SAA-C03 test video), auth, plan isolation between users, progress, YouTube lookups and security headers.

### Using PostgreSQL instead of SQLite

Create a database, then set the connection URL in `backend/.env`:

```
DATABASE_URL=postgresql+psycopg://planner:change-me@localhost:5432/planner
```

Tables are created on the next start. To run the tests against Postgres, use `TEST_DATABASE_URL=... pytest`. The Postgres path is not tested yet, because Postgres wasn't installed on the dev machine.

### Optional: YouTube Data API key

Without a key, the browser reads the length from a hidden YouTube player. That value is whole seconds only and can be 1 s high (`50:29:19` instead of `50:29:18`), and chapters must be pasted by hand. With a key, the server returns the exact length plus the chapter list:

1. Google Cloud Console → enable **YouTube Data API v3** → Credentials → API key.
2. Restrict the key to the YouTube Data API v3 API. On EC2, also restrict it to the server's IP address. HTTP-referrer restrictions don't apply to server-side calls.
3. Set `YOUTUBE_API_KEY=...` in `backend/.env` and restart.

Each lookup costs 1 quota unit (default quota: 10,000 per day). Results are cached for an hour.

## API summary (`/api/v1`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register`, `/auth/login`, `/auth/logout` | Account and session (httpOnly cookie) |
| GET | `/auth/me` | Current user |
| GET / POST | `/plans` | List or create plans |
| GET / PUT / DELETE | `/plans/{id}` | Read (includes the computed schedule), update, delete |
| PUT | `/plans/{id}/progress/{day}` | `{"done": true or false}` |
| DELETE | `/plans/{id}/progress` | Clear ticks |
| GET | `/youtube/videos/{videoId}` | Length and chapters (needs a server key) |
| GET | `/health`, `/config` | Health (includes a DB check), frontend feature flags |

Requests that change data (POST/PUT/DELETE) must send `X-Requested-With: planner`. This is the CSRF guard, and the frontend does it automatically.

## Security notes

- Passwords are hashed with Argon2. Session tokens are random, and only their SHA-256 hash is stored. Logging out deletes the session on the server.
- The cookie is `HttpOnly` and `SameSite=Lax`. Set `COOKIE_SECURE=true` once the site uses HTTPS.
- Login is rate-limited: 10 failures per email and 50 per IP in 15 minutes. The limit is kept in memory, so with several workers or servers it should move to Redis or the DB.
- Every response sends a CSP, `nosniff` and `Referrer-Policy: strict-origin-when-cross-origin`.
- Users only ever see their own plans. Another user's plan returns 404.

## Not done yet (next steps)

- Deployment to AWS EC2: nginx + systemd (or Docker), HTTPS, Postgres (RDS or on the instance), `--proxy-headers` for real client IPs.
- Email verification and password reset (needs an email service such as SES).
- Calendar export (.ics), "fell behind" rescheduling.

`legacy/standalone.html` is the original single-file version, kept for reference. On first login, the new app imports any plan and ticks that version saved in the same browser.
