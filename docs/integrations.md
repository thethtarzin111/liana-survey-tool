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
