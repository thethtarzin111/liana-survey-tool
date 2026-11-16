# Deployment (draft)

Everything is a Docker image, configured with environment variables, so it
runs on any cloud. Use an **EU region** and **demo data only**.

## Images
| Image | Dockerfile | Notes |
|---|---|---|
| admin-web | `frontend/Dockerfile` | nginx; proxies `/api` to the gateway |
| gateway | `backend/gateway/Dockerfile` | nginx, port 8000, the only public entry point; `/health` |
| survey-manager | `backend/survey-manager/Dockerfile` | port 8000 (internal), readiness `/health/ready` |
| respondent | `backend/respondent/Dockerfile` | port 8000 (internal), scale this one for newsletter bursts |
| data-analyzer | `backend/data-analyzer/Dockerfile` | port 8000 (internal), readiness `/health/ready` |
| worker | `backend/worker/Dockerfile` | no port |
| liana-connector | `backend/liana-connector/Dockerfile` | no port |

Also needed: PostgreSQL 16, RabbitMQ 3.13, and a one-off migration run with
dbmate (`backend/db/migrations`).

## Demo hosting (to be chosen)
Option if Liana confirms Google Cloud: Cloud Run in `europe-north1` (Finland)
for the images (only the gateway and admin-web public), a managed Postgres (Cloud SQL, or a free Neon/Supabase
database in an EU region) and a hosted RabbitMQ (e.g. CloudAMQP in the EU).
The worker and connector need an always-on instance, since they listen to
the queue.

Ask Liana before choosing: which cloud and stack they use.
