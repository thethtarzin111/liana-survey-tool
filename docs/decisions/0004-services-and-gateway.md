# 0004 Separate services and an API gateway, as in the report

> Runtime update: see [0005 Native development](0005-native-development.md).
> Container and nginx references below describe the former deployment.

**Status:** accepted · 2026-11-16 · replaces [0002](0002-three-processes.md)

## Context
Decision 0002 ran the survey manager, respondent endpoint and data analyzer as
modules inside one `api` process, and had no API gateway. The mid-term report,
which Liana has read, describes microservices behind an API gateway (Figure 1),
"because of scaling and fault isolation", with a stateless respondent service
that scales independently of the rest. The code and the report should agree.
The modules were still almost empty, so splitting was cheap now and would only
get more expensive with each feature.

## Decision
Run the report's components as separate containers:

| Container | Report component |
|---|---|
| `gateway` (nginx) | API Gateway: routing, auth, rate limiting |
| `survey-manager` | Survey Manager |
| `respondent` | Respondent's Survey Service |
| `data-analyzer` | Data Analyzer service |
| `worker` | Background Worker |
| `liana-connector` | Liana Connector |

They share one PostgreSQL database (the report's Survey DB, with row-level
security) and one RabbitMQ instance with separate queues. Shared Python code
(settings, tenant-safe database access, queue messages, FastAPI helpers) is
in `backend/packages/shared-py`.

## Consequences
- The respondent path can be scaled on its own during newsletter bursts.
- The gateway is the single place for login, so Liana's real authentication
  plugs in there and the services stay unchanged.
- More containers to run locally (seven app containers instead of five). The
  services are small; Docker needs about 4 GB of free memory.
- Services must not import each other's code. They talk through the gateway,
  the database tables they own, or the queues.
