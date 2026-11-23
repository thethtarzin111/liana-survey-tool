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
 | local gateway: routing and demo identity |
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

The service boundaries above are logical: local development runs the three HTTP
apps in one Python process through `backend/scripts/local_gateway.py`. The worker
and connector are optional separate Python processes using a native or hosted
RabbitMQ instance. `npm run dev` starts the native development stack.

## Report components → code

| Report component (Figure 1) | Code | Requirements (Table 2) |
|---|---|---|
| Admin web app | `frontend` | R02 |
| Development API gateway (routing, demo identity) | `backend/scripts/local_gateway.py` | R01, R05 |
| Survey Manager (surveys, links, results) | `backend/services/survey-manager` | R02, R06, R07 |
| Respondent's Survey Service (verify token, accept answer) | `backend/services/respondent` | R01, R05, R07, R08 |
| Background Worker | `backend/services/worker` | R04 |
| Data Analyzer service | `backend/services/data-analyzer` | R03, R04, R08 |
| Liana Connector (OAuth 2.0, retries, back-off) | `backend/services/liana-connector` | R08 |
| Survey DB (tenant_id + row-level security) | `backend/db/migrations` (PostgreSQL) | R05 |
| "respondent DB" | The respondent tables in the same Survey DB: `responses`, `answers`, `contact_requests` | R01, R05 |
| answers queue / integration queue | `survey.answers` / `survey.liana-events` in `liana_survey_shared/queues.py` | R01, R08 |
| Sending survey queue → LianaMailer API | Not built: the report plans it once LianaMailer's API docs arrive. Until then links go out by the HTML snippet, public link and QR code (R06, R07). | R06 |

Shared Python code lives in `backend/packages/shared-py`: settings, database access
with tenant isolation, queue message formats, and FastAPI helpers for the
HTTP services (`liana_survey_shared.web`).

## One database, separate tables

The report's text describes one Survey DB where every row has a `tenant_id`
protected by row-level security. Figure 1 also shows a "respondent DB" box;
in the code this is the respondent tables in that same database, not a
second database. Each service only touches its own tables:

| Service | Writes | Reads |
|---|---|---|
| survey-manager | `surveys`, `questions`, `templates`, `contact_requests.status` | the same, plus `contact_requests`, `responses` and `answers` for the Contact requests page |
| respondent | nothing (answers go to the queue) | `surveys`, `questions` (to show the survey) |
| worker | `responses`, `answers`, `contact_requests`, `survey_aggregates`, `response_notifications` | `questions`, `surveys`, `users` (owner of a survey, for "new responses" emails) |
| data-analyzer | nothing | `survey_aggregates`, `answers`, `contact_requests` |
| liana-connector | `contact_requests` delivery columns only (`liana_status`, `liana_attempts`, `liana_updated_at`) | the same |

A second database would mean keeping two copies of survey data in sync, which
the demo does not need. If needed later, each service can get its own
database role that may only touch its own tables.

## The API gateway

`backend/scripts/local_gateway.py` is the local development entry point, bound
to loopback on port 8000. Production ingress and authentication are not supplied
by the development launcher.

- **Routing:** `/api/v1/surveys`, `/api/v1/templates`, `/api/v1/contact-requests` → survey-manager;
  `/api/v1/results` → data-analyzer; `/r/<token>` → respondent.
- **Authentication:** for admin routes the gateway sets who the user is
  (`X-Tenant-Id`, `X-User-Id`, name, email) and always overwrites whatever the
  client sent. Respondent routes get these headers cleared. Services read the
  user with `liana_survey_shared.web.auth.current_user()`. In dev mode the user
  is the demo user from `.env`, and the gateway answers `/api/v1/me` itself
  (decision 0003). A production gateway must validate Liana's real login before
  forwarding identity to the services.
- **Rate limiting:** not implemented by the local gateway. Configure it at
  production ingress before serving real traffic.

## Queues

| Queue | From → to | Message |
|---|---|---|
| `survey.answers` (answers queue) | respondent → worker | `AnswerSubmitted` |
| `survey.liana-events` (integration queue) | data-analyzer, worker → liana-connector | `ContactRequested`, `NewResponsesDigest`, identified answers |
| `survey.dead-letter` | any → people | messages that failed |

Because a newsletter can bring thousands of clicks at once, the respondent
service only queues each answer and returns the thank-you page, while the
worker saves answers at its own pace. The two scale independently.

## Decisions

- [0001 FastAPI instead of PHP](decisions/0001-fastapi-instead-of-php.md)
- [0002 Three processes instead of five services](decisions/0002-three-processes.md) (replaced by 0004)
- [0003 Dev-auth stub, no login screen](decisions/0003-dev-auth-stub.md)
- [0004 Separate services and an API gateway, as in the report](decisions/0004-services-and-gateway.md)

The native runtime replaces the former container configuration; see
[0005 Native development runtime](decisions/0005-native-development.md).
