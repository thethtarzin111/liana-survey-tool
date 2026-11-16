# Architecture

LianaSurvey follows the architecture in the team's mid-term report (Figure 1
and Table 2): microservices with ports and adapters, an API gateway in front,
an admin app for marketers, a lightweight respondent service, queues for
answers and integration events, and one Liana connector for all Liana products.

```
 Marketer (admin-web)     Respondent (email link, public link, QR)
          │                        │
          ▼                        ▼
 ┌──────────────────────────────────────────────┐
 │ gateway (nginx)  routing · auth · rate limits│  the only entry point
 └──────┬──────────────────┬───────────────┬────┘
        │ /api/v1/surveys  │ /r/<token>    │ /api/v1/results
        │ /api/v1/templates│ (no login)    │
 ┌──────▼───────┐  ┌───────▼────────┐  ┌───▼────────────┐
 │survey-manager│  │   respondent   │  │ data-analyzer  │
 │surveys, links│  │ verify token,  │  │ NPS / CSAT,    │
 │templates     │  │ accept answer  │  │ analysed data  │
 └──────┬───────┘  └───────┬────────┘  └───┬────────▲───┘
        │                  │ answers queue │        │ read results
        │                  ▼               │        │
        │          ┌──────────────┐        │        │
        │          │    worker    │        │        │
        │          │ save answers,│        │        │
        │          │ update totals│        │        │
        │          └──────┬───────┘        │        │
        ▼                 ▼                │        │
 ┌─────────────────────────────────────────┴────────┴───┐
 │ Survey DB (PostgreSQL): tenant_id + row-level security│
 └───────────────────────────────────────────────────────┘
                                           │ integration queue
                                           ▼ (identified answers, "Contact me")
                                 ┌──────────────────┐   ┌────────────────────┐
                                 │ liana-connector  │──▶│ LianaAutomation    │
                                 │ OAuth 2.0, retry,│   │ LianaMailer (later)│
                                 │ back-off         │   └────────────────────┘
                                 └──────────────────┘
```

All boxes are separate containers (`docker-compose.yml`). One RabbitMQ
instance hosts the separate queues, as the note under the report's figure says.

## Report components → code

| Report component (Figure 1) | Code | Requirements (Table 2) |
|---|---|---|
| Admin web app | `frontend` | R02 |
| API Gateway (routing, auth, rate limiting) | `backend/gateway` (nginx) | R01, R05 |
| Survey Manager (surveys, links, results) | `backend/survey-manager` | R02, R06, R07 |
| Respondent's Survey Service (verify token, accept answer) | `backend/respondent` | R01, R05, R07, R08 |
| Background Worker | `backend/worker` | R04 |
| Data Analyzer service | `backend/data-analyzer` | R03, R04, R08 |
| Liana Connector (OAuth 2.0, retries, back-off) | `backend/liana-connector` | R08 |
| Survey DB (tenant_id + row-level security) | `backend/db/migrations` (PostgreSQL) | R05 |
| "respondent DB" | The respondent tables in the same Survey DB: `responses`, `answers`, `contact_requests` | R01, R05 |
| answers queue / integration queue | `survey.answers` / `survey.liana-events` in `liana_survey_shared/queues.py` | R01, R08 |
| Sending survey queue → LianaMailer API | Not built: the report plans it once LianaMailer's API docs arrive. Until then links go out by the HTML snippet, public link and QR code (R06, R07). | R06 |

Shared Python code lives in `backend/shared-py`: settings, database access
with tenant isolation, queue message formats, and FastAPI helpers for the
HTTP services (`liana_survey_shared.web`).

## One database, separate tables

The report's text describes one Survey DB where every row has a `tenant_id`
protected by row-level security. Figure 1 also shows a "respondent DB" box;
in the code this is the respondent tables in that same database, not a
second database. Each service only touches its own tables:

| Service | Writes | Reads |
|---|---|---|
| survey-manager | `surveys`, `questions`, `templates` | the same |
| respondent | nothing (answers go to the queue) | `surveys`, `questions` (to show the survey) |
| worker | `responses`, `answers`, `contact_requests`, `survey_aggregates` | `questions` |
| data-analyzer | nothing | `survey_aggregates`, `answers`, `contact_requests` |

A second database would mean keeping two copies of survey data in sync, which
the demo does not need. If needed later, each service can get its own
database role that may only touch its own tables.

## The API gateway

`backend/gateway` is nginx. It is the only container reachable from outside
in production.

- **Routing:** `/api/v1/surveys`, `/api/v1/templates` → survey-manager;
  `/api/v1/results` → data-analyzer; `/r/<token>` → respondent.
- **Authentication:** for admin routes the gateway sets who the user is
  (`X-Tenant-Id`, `X-User-Id`, name, email) and always overwrites whatever the
  client sent. Respondent routes get these headers cleared. Services read the
  user with `liana_survey_shared.web.auth.current_user()`. In dev mode the user
  is the demo user from `.env`, and the gateway answers `/api/v1/me` itself
  (decision 0003). Liana's real login plugs in at the gateway with
  `auth_request`, and the services do not change.
- **Rate limiting:** per client IP, with more room on the answer path for
  newsletter bursts. Over the limit returns 429.

## Queues

| Queue | From → to | Message |
|---|---|---|
| `survey.answers` (answers queue) | respondent → worker | `AnswerSubmitted` |
| `survey.liana-events` (integration queue) | data-analyzer → liana-connector | `ContactRequested`, identified answers |
| `survey.dead-letter` | any → people | messages that failed |

Because a newsletter can bring thousands of clicks at once, the respondent
service only queues each answer and returns the thank-you page, while the
worker saves answers at its own pace. The two scale independently.

## Decisions

- [0001 FastAPI instead of PHP](decisions/0001-fastapi-instead-of-php.md)
- [0002 Three processes instead of five services](decisions/0002-three-processes.md) (replaced by 0004)
- [0003 Dev-auth stub, no login screen](decisions/0003-dev-auth-stub.md)
- [0004 Separate services and an API gateway, as in the report](decisions/0004-services-and-gateway.md)
