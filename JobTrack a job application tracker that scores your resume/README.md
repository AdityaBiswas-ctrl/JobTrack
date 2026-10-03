# JobTrack

JobTrack is a FastAPI and MySQL job application tracker with authentication,
application history, reminders, resume scoring, and dashboard statistics.

## Start the API and database

1. Copy `.env.example` to `.env`, replace the local database passwords, and
   set `JWT_SECRET` to a random value of at least 32 bytes.
2. Run `docker compose up --build`.
3. Open `http://localhost:8000/health`. A healthy API returns `{"status":"ok"}`.

To run the backend tests locally:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m pytest
```

The ATS scorer contract is documented in [docs/scorer_contract.md](docs/scorer_contract.md)
and was verified against the local scorer source. Set `SCORER_URL` to the scorer
base URL (for example `http://localhost:8001`) and
`SCORER_TIMEOUT_SECONDS` to the request timeout; it defaults to 30 seconds.

## Authentication

Sign up with `POST /api/auth/signup`, then open `/docs` and use **Authorize**.
Enter the signup email in the OAuth2 form's `username` field and the password
in its `password` field. The login endpoint accepts this form and returns a
short-lived bearer token. `JWT_SECRET` must be set to a random value of at least
32 bytes.

## Applications API

Authenticated application endpoints are under `/api/applications`. Create an
application with `POST`; list with `GET` and optional `status`, `q`, `limit`
(default 20, maximum 100), and `offset` query parameters. Lists are ordered by
creation time descending, then ID descending, and include `items`, `total`,
`limit`, and `offset`. Use `GET`, `PATCH`, or `DELETE /api/applications/{id}`
for one application. Updates cannot change status; a dedicated status endpoint
records every transition in history. Application lookups are always scoped to the
authenticated user and return 404 for records they do not own.
History, reminder, and score foreign keys use `ON DELETE CASCADE` so deleting an
application removes dependent rows as well.

## Status history and reminders

`PATCH /api/applications/{id}/status` changes status and appends a history
record in one database transaction. Creating an application also records its
initial transition from an empty status to `wishlist`. Repeating the current
status returns the application without adding a duplicate history row.
`GET /api/applications/{id}/history` returns events from oldest to newest.

Create a reminder with `POST /api/applications/{id}/reminders`; `due_at` must
include a timezone and is normalized to UTC. `GET /api/reminders?due=true`
returns only incomplete reminders due now or earlier, ordered by due time;
without `due=true`, it lists all reminders for the current user with
`limit`/`offset` pagination. Both forms include the related company and role.
`PATCH /api/reminders/{id}/done` is idempotent. Reminder ownership is checked
through its application, and deleting an application cascades to its history
and reminders. The due-time index is on `due_at`; a composite `(done, due_at)`
index may be worth measuring with MySQL `EXPLAIN` once the table has realistic
data.

## Resumes and scoring

Upload PDFs with `POST /api/resumes` using multipart form fields `file` and
`label`. Files are checked for the `%PDF-` signature and capped at 2 MB; each
account can store up to five resumes. JobTrack stores the bytes in MySQL and
does not write uploaded filenames to disk.

Score an application with `POST /api/applications/{id}/score` and JSON
`{"resume_id": 1}`. The scorer receives the resume and the application's job
description using the verified ATS multipart fields. Successful normalized
resume/job-description pairs are cached; failures are saved for score history
but are never reused as cache hits. Scorer timeouts and errors return 503 while
other JobTrack routes remain available. The scorer may be waking up, and with
the default 30-second timeout plus one retry a score request may take about a
minute. `GET /api/applications/{id}/scores` returns score history.

Scoring is limited to 10 uncached attempts per user per hour using an
in-memory counter. The counter resets on API restart and is not shared across
multiple API instances; a distributed deployment would need a shared limiter.

## Dashboard statistics

`GET /api/stats` is scoped to the authenticated user and returns:

- **Counts by status:** current application rows grouped by status. Every
  supported status is returned, with zero when there are no matching rows.
- **Applications per week:** applications grouped by `applied_on` into
  Monday-starting weeks, for the current week and the previous 11 weeks.
  Missing weeks are included with count zero; applications without an
  `applied_on` date are not counted.
- **Response rate:** among applications whose current status is not
  `wishlist`, the percentage that ever reached `online_assessment`,
  `interview`, `offer`, or `rejected` in status history. A later rejection
  still counts as a response; `withdrawn` alone does not.
- **Days to first response:** average and median UTC calendar-day differences
  from `applied_on` to the earliest response history timestamp. Both are
  `null` when there are no response dates. The stat is only as accurate as the
  dates and history entered; backfilled applications with newly entered
  history can skew it.

The current-week boundary is based on UTC `today` passed into the stats
calculation. Week aggregation is performed on SQL-grouped application dates,
then bucketed in Python to keep the implementation compatible with SQLite test
databases and MySQL.

Create the hand-countable local data set from `backend` with
`python -m scripts.seed_demo_data` (six applications). For the P9 latency run,
use `python -m scripts.seed_demo_data --count 1000`. The seed is for local
demonstrations and benchmarking only. Re-running it replaces only the
`demo@jobtrack.local` account and its associated data; its local demo password
is `demo-password`.

## React frontend

The React 18 and TypeScript frontend lives in `frontend/`. From the repository
root, start the API using the setup above, then run:

```powershell
cd frontend
npm ci
npm run generate:api
npm run dev
```

Vite serves the UI at `http://localhost:5173` and proxies `/api` to
`http://127.0.0.1:8000`, so local development does not need browser CORS
configuration. The generated `src/api/generated.ts` types come from FastAPI's
`/openapi.json`; regenerate them when the API contract changes.

To run frontend checks and create the production build:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
```

The UI uses TanStack Query for server data and invalidates affected queries
after mutations. The central API client stores the bearer token in memory and
`sessionStorage`, which keeps a session across refreshes in the same tab but
means an XSS vulnerability could read it. React renders user-entered notes and
job descriptions as text; the UI does not use `dangerouslySetInnerHTML`.

Set `ALLOWED_ORIGINS` to a comma-separated list of exact browser origins
(scheme and host, without a trailing slash) when serving the API and frontend
from different origins. Wildcard origins are rejected. `VITE_API_URL` is
embedded in the frontend at build time; changing it requires rebuilding the
frontend image or static site. For the included Docker Compose setup, the UI
is served on `http://localhost:3000` and its nginx proxy forwards `/api` to the
API.

The signup page and any public demo should use sample data only. Do not upload
your real resume or enter real applications into a public instance.
