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

Needs Docker Desktop.

```sh
cp .env.example .env        # then change the passwords
docker compose up --build
```

| What | URL |
|---|---|
| Admin app | http://localhost:4200 |
| API docs (Swagger) | http://localhost:8000/docs |
| RabbitMQ console | http://localhost:15672 |

There is no login screen: everyone is the demo user (see `docs/decisions/0003-dev-auth-stub.md`).

## Develop

```sh
# Python (3.12+), from the repo root
python -m venv .venv
.venv/Scripts/activate        # Windows (Git Bash: source .venv/Scripts/activate)
make install-py               # or copy the pip commands from the Makefile
make test-py

# Frontend
cd apps/admin-web
npm install
npm run dev                   # http://localhost:4200, talks to the API on :8000
npm test
```

`make` is not installed on Windows by default. Use Git Bash or WSL, or run
the commands from the `Makefile` by hand. CI only calls `make` targets.

## Repo layout

| Folder | What |
|---|---|
| `apps/admin-web/` | React + TypeScript admin app (one folder per sidebar item in `src/features/`) |
| `services/api/` | FastAPI: survey manager, analytics, respondent endpoint (as modules) |
| `services/worker/` | Saves answers from the queue and updates totals |
| `services/liana-connector/` | The only part that talks to Liana products (ports and adapters) |
| `packages/shared-py/` | Settings, tenant-safe DB access, queue message formats |
| `db/` | Plain SQL migrations (dbmate), demo seed data, RLS check |
| `infra/` | Postgres init, RabbitMQ and deployment config |
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
