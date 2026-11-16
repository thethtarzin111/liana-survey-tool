# Handoff to Liana

For Liana's developers taking over LianaSurvey.

## Two ways to take it over

**A. Run it as its own service.** Deploy the Docker images next to Liana's
products (`docs/deployment.md`). Replace the dev-auth stub with Liana's login
(`docs/decisions/0003-dev-auth-stub.md`) and switch the connector to the real
adapters. No rewrite needed.

**B. Rebuild it inside Liana's codebase (e.g. PHP).**

| Part | Reuse |
|---|---|
| `apps/admin-web` (React + TS) | As is |
| `db/migrations` (plain SQL) | As is |
| `docs/api/openapi.yaml` | As is: a new backend implements the same contract |
| `tests/e2e`, `tests/contract`, `db/tests` | As is: they test over HTTP / SQL |
| `*/domain.py` (NPS, CSAT, survey rules) | Translate: plain code, no framework |
| Queue message formats (`messages.py`) | Translate: they are documented contracts |
| FastAPI routes, worker, connector | Rewrite in the new language |

A port is done when the new backend passes `tests/e2e` and `tests/contract`.

## CI
GitHub Actions only calls `make` targets (`make lint`, `make test`,
`make e2e`). Moving to GitLab CI means a few `script:` lines calling the same
targets.

## What is still open
See the open issues on the GitHub Project board (https://github.com/users/thethtarzin111/projects/1). Integration status is in `docs/integrations.md`, and
open privacy questions are in `docs/gdpr.md`.
