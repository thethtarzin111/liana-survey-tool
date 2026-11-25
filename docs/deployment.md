# Deployment

The repository supports a native development stack. Container build files and
the former Compose stack have been removed. Use an EU region and demo data
for demonstrations.

## Local demo

Install Node.js, Python 3.12+ and PostgreSQL binaries, then run `npm install`
and `npm run dev` at the repository root. The launcher prepares the database,
applies migrations, seeds demo data and starts Vite and the Python API gateway.
See the root README for independent frontend/backend commands.

## Demo server

A shared demo for the Liana team and other students runs on one small EU VM
(Azure for Students), deployed by the "Deploy demo" workflow after CI passes on
`main`. It runs the local gateway with demo data behind HTTPS, with a login page
and one demo login per organisation; survey links stay public. Setup and day-to-day use:
`backend/infra/deploy/README.md`. It is a demo, not production: there is no real
login yet.

## Hosted deployment

For a production setup (e.g. on Liana's own infrastructure), the source layout is:

| Component | Source / build | Runtime |
|---|---|---|
| Admin app | `frontend/`, `npm ci && npm run build` | Static hosting of `frontend/dist` with SPA fallback |
| Survey manager | `backend/services/survey-manager` | `uvicorn survey_manager.main:app` |
| Respondent | `backend/services/respondent` | `uvicorn respondent_service.main:app` |
| Data analyzer | `backend/services/data-analyzer` | `uvicorn data_analyzer.main:app` |
| Worker | `backend/services/worker` | `python -m survey_worker.main` |
| Liana connector | `backend/services/liana-connector` | `python -m liana_connector.main` (queue) and `uvicorn liana_connector.api:app` (Integrations page API) |

Install `backend/packages/shared-py` and the relevant service dependencies into
the deployed Python environment. Configure each HTTP service's listening host
and port for its hosting platform, and supervise long-running processes.

A production entry point must route `/api/v1/surveys` and `/api/v1/templates`
to the survey manager, `/api/v1/results` to the analyzer, `/api/v1/integrations`
to the connector's API, and `/r/` to the respondent. It must authenticate admin requests, provide `/api/v1/me`, replace
forwarded identity headers, provide TLS and rate limits, and keep the individual
services private. `backend/scripts/local_gateway.py` is a loopback-only demo
entry point and does not implement production authentication.

Provision persistent PostgreSQL separately. Apply `backend/db/migrations` using
dbmate as the schema owner before starting services. Configure `DATABASE_URL`
for a separate restricted app role so row-level security remains effective.
Load `backend/db/seed/seed.sql` only for a demo deployment. Native role setup
for a fresh database is in `backend/infra/postgres/init/01-app-role.sh`.

The optional worker and connector require native or hosted RabbitMQ and
`RABBITMQ_URL`. Store database passwords and integration credentials in the
hosting platform's secret store. Do not deploy the generated `.local` database,
its passwords, or the Vite development server as the production setup.

Migrations and the demo data can be applied with
`python -m backend.scripts.prepare_db` (needs `OWNER_DATABASE_URL` and
`APP_DB_PASSWORD`), as the demo server does.

A future Cloud Run deployment can use Google's source builds without local
Docker tooling; cloud-specific routing, IAM and database configuration still
need to be implemented. Confirm the production hosting with Liana.
