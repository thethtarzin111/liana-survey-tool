# LianaSurvey

A survey and feedback tool for Liana customers, built by a student team
(holistic course) with Liana as the partner organisation. It works next to
LianaMailer and LianaAutomation: marketers create a survey, send it in a
newsletter or by link, and see NPS / CSAT results. "Contact me" requests can
start a LianaAutomation flow.

> **Status:** scaffolding only. Every page and service exists and starts, but
> features are built one issue at a time. Uses demo data only
> (Example Members Association, Anna Virtanen).

## Run it

### Local development

Install Node.js, Python 3.12+ (available as `python`), and PostgreSQL including
its command-line tools. On Windows the launcher finds PostgreSQL under
`C:\Program Files\PostgreSQL`; elsewhere put its `bin` directory on PATH, or
set `POSTGRES_BIN` to that directory. No PostgreSQL service needs to be configured.

From the repository root:

```sh
npm install
npm run dev
```

To run them separately, use two terminals from the repository root:

```sh
# Terminal 1: backend and local PostgreSQL
cd backend
npm install
npm run dev
```

```sh
# Terminal 2: frontend
cd frontend
npm install
npm run dev
```

The frontend calls the backend through Vite's `/api` proxy. You can also use
`npm run dev:backend` and `npm run dev:frontend` from the repository root.
The root `npm run dev` still starts both together.

`npm install` creates `.venv`, installs all Python services, and installs the
frontend dependencies. Set `PYTHON` before installation to select another Python
executable if needed. Downloads require internet access.

`npm run dev` creates a private PostgreSQL cluster on `127.0.0.1:55432`, applies
pending SQL migrations, loads demo data, and starts the real backend APIs on
http://localhost:8000 and Vite on http://localhost:4200. It uses a separate app
database role so tenant row-level security still applies. Data and generated
passwords persist in the ignored `.local/` directory. Ctrl+C stops the servers
and database. `LOCAL_POSTGRES_PORT` overrides the database port if necessary.
Do not run two local launchers at once, or switch PostgreSQL major versions for
an existing cluster without migrating its data.
Survey API documentation is available at http://localhost:8000/docs.

The local gateway runs the existing service apps in one Python process. It uses
the demo identity and is for local development only. Production authentication,
TLS and rate limiting must be configured separately. It does not add features
missing from the scaffold (for example, the results and respondent endpoints
are still placeholders).

Answers work without RabbitMQ locally: the local gateway hands each answer
straight to the worker's save code in the same process (the same code the worker
runs on the real queue). To use a real RabbitMQ and the worker and connector
processes instead, install RabbitMQ, set `RABBITMQ_URL` in `.env` or your
environment, and set `LOCAL_QUEUE_WORKERS=1` before `npm run dev`. The local
launcher does not change `.env`.

"New responses" emails work the same way: without RabbitMQ the local gateway
also runs the worker's sweep and hands each email to the connector's mock mail
adapter, which prints it in the backend terminal (`[mock mail] ...`). For a
quick demo, start with `RESPONSE_DIGEST_INTERVAL_SECONDS=60 npm run dev`, tick
"Notify me of new responses by email" on a live survey and answer it a few times.

#### Try answering a survey

1. `npm run dev`, then open http://localhost:8000/docs.
2. Create a survey from a template (`POST /api/v1/templates/{id}/surveys`),
   publish it (`POST /api/v1/surveys/{id}/publish`) and get answer links for
   made-up readers (`POST /api/v1/surveys/{id}/test-links`, local development only).
3. Open a link with an answer added, e.g. `…&a=9` for NPS, `&a=2` for thumbs
   ("Loved it") or `&a=4` for CSAT. You get the thank-you page, and the survey's
   Answers and Headline score on the Surveys page count it. Opening the same
   link again does not count twice; each test link is a different reader.

| What | URL |
|---|---|
| Admin app | http://localhost:4200 |
| API gateway | http://localhost:8000 |
| Survey API docs | http://localhost:8000/docs |
| Backend readiness | http://localhost:8000/health/ready |

The backend is the mid-term report's architecture: an API gateway in front of
separate services. See [`docs/architecture.md`](docs/architecture.md).

There is no login screen: everyone is a demo user (see `docs/decisions/0003-dev-auth-stub.md`).
The demo data has two organisations, Example Members Association (Anna Virtanen, the
default) and Example Sports Club (Mikko Korhonen). **Switch organization (demo)** in the
user menu changes between them, to show that organisations never see each other's data.

## Develop

```sh
# Python (3.12+), from the repo root
python -m venv .venv
.venv/Scripts/activate        # Windows (Git Bash: source .venv/Scripts/activate)
make install-py               # or copy the pip commands from the Makefile
make test-py

# Frontend
cd frontend
npm install
npm run dev                   # http://localhost:4200, talks to the gateway on :8000
npm test
npm run lint                  # ESLint; also blocks hard-coded colours (use the design tokens)
```

The frontend has no API URL setting: it always calls `/api/...` on its own address.
`npm run dev` forwards those calls to the local API gateway on port 8000
(`frontend/vite.config.ts`). A deployed frontend needs equivalent API routing.

`make` is not installed on Windows by default. Use Git Bash or WSL, or run
the commands from the `Makefile` by hand. CI uses the same native tools and Makefile checks.

## Repo layout

| Folder | What |
|---|---|
| `frontend/` | React + TypeScript admin app (one folder per sidebar item in `src/features/`) |
| `backend/scripts/` | Native launcher and development API gateway (demo identity) |
| `backend/services/survey-manager/` | FastAPI: surveys, questions, templates, publishing, links |
| `backend/services/respondent/` | FastAPI: public answer path (verify link, queue answer, thank-you page) |
| `backend/services/data-analyzer/` | FastAPI: NPS/CSAT results; sends contact requests to the integration queue |
| `backend/services/worker/` | Saves answers from the queue and updates totals |
| `backend/services/liana-connector/` | The only part that talks to Liana products (ports and adapters) |
| `backend/packages/shared-py/` | Settings, tenant-safe DB access, queue message formats, FastAPI helpers |
| `backend/db/` | Plain SQL migrations (dbmate), demo seed data, RLS check |
| `backend/infra/` | Postgres init, RabbitMQ and deployment config |
| `design/` | Prototype snapshot and design tokens (reference only) |
| `docs/` | Architecture, API, data model, integrations, GDPR, handoff to Liana |
| `tests/e2e/` | Playwright tests against the running stack |

## Working agreement

- Work on a branch, open a pull request, never push to `main`.
- One issue per PR. Link the GitHub issue in the PR (for example "Closes #24").
- CI must be green: lint, unit tests, DB migrations + RLS check, E2E.
- Never commit `.env` or any Liana staging login.

## For Liana's developers

Start with [`docs/handoff.md`](docs/handoff.md).

## Design prototype

Link: https://claude.ai/artifact/UFF9k3NRNRJoUHiHmyJqer#play-15dd8cd198dd
