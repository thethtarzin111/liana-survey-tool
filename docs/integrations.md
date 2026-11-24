# Integrations with Liana products

All calls to Liana go through `backend/services/liana-connector`. The rest of the
system only publishes messages to RabbitMQ.

| Integration | How | Status |
|---|---|---|
| Survey in a LianaMailer newsletter | Copy-paste HTML snippet (R06, #40): one link per answer, with LianaMailer's `$id$` placeholder as the reader (so each reader counts once) and campaign/segment tags. Not signed, because a pasted snippet is the same for everyone, so only surveys whose snippet was made accept unsigned links; signed links through the LianaMailer API are #118. | `POST /api/v1/surveys/{id}/snippet`; needs no Liana API |
| "Contact me" → LianaAutomation | `ContactRequested` message → connector → LianaAutomation `POST /import` with `no_duplicates` | Mock adapter. Waiting for a working LianaAutomation test account |
| "New responses" emails to a survey's owner | `NewResponsesDigest` message (worker → connector) → `NotificationMail` port | Mock adapter (logs the email). No real mail adapter yet |
| Send surveys through LianaMailer API | `MailDelivery` port + LianaMailer adapter | Placeholder. No LianaMailer API docs yet |
| Save answers to contact attributes | Through LianaAutomation or LianaMailer API | Not started |

## "New responses" emails

When a survey's "Notify me of new responses by email" (`notify_on_response`) is
on, its owner (the app user in `surveys.created_by`) gets an email about new
responses:

- The first new response is emailed right away.
- Responses within the next interval are held. Once the interval has passed
  since the last email, they go out as one digest. No new responses, no email.
- The interval is `RESPONSE_DIGEST_INTERVAL_SECONDS` (default 3600). The worker
  checks for held responses every `RESPONSE_DIGEST_SWEEP_SECONDS` (default 60).
- The email has the survey title, the counts and a link to the results
  (`APP_BASE_URL/results?survey=<id>`). Never answers or anything about readers.

The worker tracks per survey when the last email went out and how many responses
it covered (`response_notifications`). It claims an email in the database before
it publishes `NewResponsesDigest` to `survey.liana-events`, so two workers never
send the same one. The connector turns the message into an email and sends it
through the `NotificationMail` port (`NOTIFICATION_MAIL_ADAPTER`, only `mock`).

`NewResponsesDigest` fields: `tenant_id`, `survey_id`, `survey_title`,
`new_responses` (since the last email), `total_responses`, `results_url`,
`recipient_email`, `recipient_name`, `type` = `responses.digest`.

The recipient's address is an app user's address, not a reader's. It is read from
`users` when the email is due and only travels in the queue message; it is not
stored anywhere new.

## LianaAutomation (from the API docs the team has)
- Host: `https://rest.automation.lianacloud.com/api/v1`, OAuth 2.0 Bearer token.
- HMAC-SHA256 signing is deprecated and ends 31 Dec 2026; do not implement it.
- `POST /import` with `no_duplicates`, so a retried message is not recorded twice.

## Integrations page: connecting LianaAutomation

The admin connects their own LianaAutomation account on the Integrations page, in
five steps: credentials (OAuth client ID and secret, scope `automation-api`), test
connection (`/pingpong`), channel (`/channel/list`, `/channel/create`), what to send,
and a test event (`/import` for a made-up `@example.com` contact). The connector's
HTTP API does the calls (`liana_connector/automation`), because only the connector
talks to Liana.

- The secret is encrypted with `INTEGRATION_SECRET_KEY` before it is stored; the
  page only ever shows its last 4 characters. Outside `AUTH_MODE=dev` the connector
  API refuses to start (and to save secrets) when the key is the default from the
  repo or shorter than 32 characters.
- Only `*.lianacloud.com` hosts are accepted, so a saved host cannot make the
  backend send the secret anywhere else. In dev mode the host `demo` is a built-in
  fake LianaAutomation (client `demo-client`, secret `demo-secret`). Outside dev
  mode a saved demo connection is refused when it is used, so it can never record
  "Sent" for an event that did not leave the server.
- Every event is a row in `integration_events`: the sync log, with Retry for failed
  ones. A retry sends the same data with `no_duplicates`, so Liana never counts it
  twice, and it first moves the row to `pending` in one statement, so a double
  click sends once. The checks that can refuse a send (connected, channel chosen,
  secret readable) run before that, and an unexpected error while sending puts the
  row back to `failed`, so an event is never left `pending` with no way to retry it.
- Errors: 401 gets a new token and one retry; 400 and a non-JSON answer fail
  without retry; 404 marks the connection as broken; 5xx, timeouts and failed
  connections (DNS, outage) fail so they can be retried, without marking a correct
  connection as broken.
- Not built yet: a role check. Any signed-in member of the organisation can
  connect, disconnect or retry; with real authentication only admins should.
- Not built yet: the worker writing an event for each identified answer (outbox)
  and the connector sending them in batches with back-off.

## Switching adapters
`LIANA_ADAPTER=mock` (default) or `LIANA_ADAPTER=lianaautomation` in `.env`.
Credentials go in `.env` locally or GitHub secrets in CI, never in the repo.

## Test environments Liana gave the team
LianaCloud account (staging), LianaMailer (testing) and LianaMonitor (staging).
Logins are kept in the team's password manager, not here.

## Email link scanners

Some mail systems (e.g. company security gateways) open every link in an email
before the reader sees it, and one-tap links answer on open. So the latest tap
per reader counts (#126): the worker replaces a reader's answer with a newer one
and moves the totals with it. Scanners open links on delivery and people tap
later, so the person's answer wins. Messages are ordered by their `created_at`,
so an older answer delivered late (e.g. after a retry) does not replace a newer one.

## Distribution channel

`AnswerSubmitted` carries `channel`: `email`, `link` or `qr` (default `link`).
The respondent service takes it from the link's `ch` parameter. Without one, an
answer link (`a=`) counts as `email` and a plain visit as `link`. The worker
stores it on the response, and survey performance (#12) groups by it.

`AnswerSubmitted` also carries `segment` (default `all`), from the link's `seg`
parameter: a newsletter segment tag such as `members`. `none` and `other` are
reserved (they are the Results filter values). An invalid or reserved `seg` shows
the incomplete-link page (400), and the snippet endpoint refuses them too. The worker stores it on the
response, and the Results page (#15) filters by it.
