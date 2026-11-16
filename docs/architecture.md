# Architecture

LianaSurvey follows the design in the team's report: ports and adapters, an
admin app for marketers, a lightweight respondent endpoint, a queue for
answers, and one integration point for all Liana products.

```
                 ┌──────────────┐
 Marketer ──────▶│  admin-web   │ React + TS (nginx)
                 └──────┬───────┘
                        │ /api/v1 (JSON)
                 ┌──────▼───────┐        ┌──────────────┐
 Respondent ────▶│     api      │───────▶│  PostgreSQL  │ tenant_id + RLS on every row
 (link / email)  │  FastAPI     │        └──────▲───────┘
                 └──────┬───────┘               │
                        │ survey.answers        │
                 ┌──────▼───────┐               │
                 │   RabbitMQ   │◀──────┐       │
                 └──────┬───────┘       │       │
                        │               │ survey.liana-events
                 ┌──────▼───────┐       │       │
                 │    worker    │───────┘───────┘ saves answers, updates totals
                 └──────────────┘
                 ┌──────────────────┐   ┌────────────────────────────┐
  RabbitMQ ─────▶│ liana-connector  │──▶│ LianaAutomation (POST /import)
                 │ ports + adapters │   │ LianaMailer (planned)      │
                 └──────────────────┘   └────────────────────────────┘
```

## Report components → code

| Report component | Code | Requirements |
|---|---|---|
| Admin web app | `apps/admin-web` | R02 |
| API gateway (auth, rate limits) | `services/api/survey_api/auth` (dev stub). Rate limits: added at deployment | R05 |
| Survey Manager | `services/api/survey_api/modules/surveys` | R02, R06, R07 |
| Respondent Survey Service | `services/api/survey_api/modules/respondent` | R01 |
| Data Analyzer | `services/api/survey_api/modules/analytics` | R03 |
| Background Workers | `services/worker` | R04 |
| Liana Connector | `services/liana-connector` | R08 |
| Survey DB | `db/migrations` (PostgreSQL, RLS) | R05 |
| RabbitMQ | one instance, queues in `liana_survey_shared/queues.py` | R01, R08 |

The report describes these as separate microservices. In code they run as
**three processes** (api, worker, connector). See
[decisions/0002](decisions/0002-three-processes.md).

## Queues

| Queue | From → to | Message |
|---|---|---|
| `survey.answers` | api (respondent) → worker | `AnswerSubmitted` |
| `survey.liana-events` | worker → liana-connector | `ContactRequested` |
| `survey.dead-letter` | any → people | messages that failed |

## Decisions

- [0001 FastAPI instead of PHP](decisions/0001-fastapi-instead-of-php.md)
- [0002 Three processes instead of five services](decisions/0002-three-processes.md)
- [0003 Dev-auth stub, no login screen](decisions/0003-dev-auth-stub.md)
