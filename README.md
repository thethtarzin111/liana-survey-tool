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
| API gateway (the only entry point) | http://localhost:8000 |
| API docs (Swagger), per service | http://localhost:8001/docs (survey-manager), :8002/docs (respondent), :8003/docs (data-analyzer) |
| RabbitMQ console | http://localhost:15672 |

The backend is the mid-term report's architecture: an API gateway in front of
separate services. See [`docs/architecture.md`](docs/architecture.md).

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
npm run dev                   # http://localhost:4200, talks to the gateway on :8000
npm test
npm run lint                  # ESLint; also blocks hard-coded colours (use the design tokens)
```

The frontend has no API URL setting: it always calls `/api/...` on its own address.
`npm run dev` forwards those calls to the API gateway on http://localhost:8000 (`vite.config.ts`),
and in Docker nginx forwards them to the `gateway` container (`apps/admin-web/nginx.conf`).

`make` is not installed on Windows by default. Use Git Bash or WSL, or run
the commands from the `Makefile` by hand. CI only calls `make` targets.

## Repo layout

| Folder | What |
|---|---|
| `apps/admin-web/` | React + TypeScript admin app (one folder per sidebar item in `src/features/`) |
| `services/gateway/` | API gateway (nginx): routing, auth (dev: demo user), rate limiting |
| `services/survey-manager/` | FastAPI: surveys, questions, templates, publishing, links |
| `services/respondent/` | FastAPI: public answer path (verify link, queue answer, thank-you page) |
| `services/data-analyzer/` | FastAPI: NPS/CSAT results; sends contact requests to the integration queue |
| `services/worker/` | Saves answers from the queue and updates totals |
| `services/liana-connector/` | The only part that talks to Liana products (ports and adapters) |
| `packages/shared-py/` | Settings, tenant-safe DB access, queue message formats, FastAPI helpers |
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
