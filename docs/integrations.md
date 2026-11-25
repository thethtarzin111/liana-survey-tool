# Integrations with Liana products

All calls to Liana go through `backend/services/liana-connector`. The rest of the
system only publishes messages to RabbitMQ.

| Integration | How | Status |
|---|---|---|
| Survey in a LianaMailer newsletter | Copy-paste HTML snippet (R06, #40): one link per answer, with LianaMailer's `$id$` placeholder as the reader (so each reader counts once) and campaign/segment tags. Not signed, because a pasted snippet is the same for everyone, so only surveys whose snippet was made accept unsigned links; signed links through the LianaMailer API are #118. | `POST /api/v1/surveys/{id}/snippet`; needs no Liana API |
| "Contact me" → LianaAutomation | `ContactRequested` message (worker) → connector → LianaAutomation `POST /import` with `no_duplicates` | Through each organisation's connection (`LIANA_ADAPTER=lianaautomation`) |
| Identified answers → LianaAutomation | `AnswerRecorded` message (worker) → connector → `survey_answered` event | Through each organisation's connection; anonymous answers are listed as "Not sent" |
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
- Not built yet: an outbox (the worker writes the event in the answer's
  transaction instead of publishing it afterwards) and sending in batches. Today
  a message lost between the worker and the connector leaves no sync log row.

## Answers from newsletter links: the follow-up page

An answer link (`/r/<token>?r=<contact id>&c=<campaign>&seg=<segment>&a=<answer>`)
opens the follow-up page. Opening it saves nothing, because email security
scanners open every link in a newsletter; the page saves the tapped answer itself
with a POST as soon as it shows (without JavaScript the reader presses Submit).
Below it are the survey's other questions (all optional there), the "Tell us
more" box (`comment_field`, when the survey has no text question; stored in
`responses.comment`) and the "Contact me" box (`contact_opt_in`). Submit updates
the same response: the reader still counts once.

The answer keeps the contact id from `r=` only when the survey is set to
identified answers (Survey settings, `surveys.anonymous` off; the page tells the
reader) or the reader ticks "Contact me" (`liana_survey_shared.contact`). The
public link and the QR code have no contact, so their page has no "Contact me".

`AnswerSubmitted` also carries `comment`, `contact_me` and `campaign` (the link's
`c`, a lowercase tag; an invalid one is left out).

After saving, the worker publishes to `survey.liana-events`:

- `AnswerRecorded` for every saved or changed answer: `tenant_id`, `survey_id`,
  `response_id`, `survey_title`, `main_kind`, `score`, `campaign`, `contact_ref`
  (null when anonymous), `type` = `answer.recorded`. Never the answers' texts.
- `ContactRequested` when the reader ticked "Contact me" and the answer has a
  contact. The contact request is created in the same transaction, once per
  response. LianaAutomation is where the customer follows up; the survey tool
  has no list of contact requests.

With `LIANA_ADAPTER=lianaautomation` and the organisation's "Survey answers"
switch on, the connector turns `AnswerRecorded` into one sync log row per response:

```json
{"identity": {"lianamailer_id": "4084399"},
 "events": [{"verb": "survey_answered",
             "items": {"survey_id": "…", "survey_name": "…", "score": "9",
                       "nps_group": "promoter", "campaign": "november"}}]}
```

- Anonymous answer: the row is "Not sent" (`skipped`) with "Not sent: anonymous
  answer." A contact id that is not a number: "Not sent: contact unknown (r=…)."
  These rows can't be retried; they show why the answer stayed in the survey tool.
- The same answer again (the follow-up form, a second tap) is not sent again. A
  changed answer updates the row and is sent again.
- Not tested yet, or no channel: failed with the reason, and Retry.
- Not checked yet: what LianaAutomation does with a contact id it doesn't know.
  Without the LianaMailer API (#118) the survey tool can't check a contact id
  itself, so a numeric id that is not a real contact is sent like any other.

The demo server runs `LIANA_ADAPTER=lianaautomation` (set by `deploy.sh` in the
release's `.env`), so the sync log there shows real answers.

## "Contact me" requests to LianaAutomation (#72)

With `LIANA_ADAPTER=lianaautomation`, each `ContactRequested` message becomes a
`survey_contact_request` event on the contact's timeline, sent through the
organisation's own connection from the Integrations page:

```json
{"identity": {"lianamailer_id": "<contact_ref>"},
 "events": [{"verb": "survey_contact_request",
             "items": {"survey_id": "…", "contact_request_id": "…", "requested_at": "…"}}]}
```

- Skipped when the organisation has not connected LianaAutomation or switched
  "Contact me" requests off.
- Every request is a row in the sync log (`integration_events`). A redelivered
  message reuses its row and is not sent again once it was sent.
- Not tested yet, or no channel: the row is failed with the reason, and the admin
  presses Retry after fixing it.
- 5xx and timeouts: the row is `retrying` and the port's `TemporaryError` is raised,
  so the connector retries with back-off (#58, see "Retries" below). Bad data, a
  wrong host or wrong credentials: the row is failed, the connection shows the
  error, and the message goes to the dead-letter queue (`DeliveryFailed`).
- To check with Liana: the identity name (`lianamailer_id`). The survey tool never
  stores email addresses, so a contact is matched on its LianaMailer contact id.

## Retries (#58)

When a port raises `TemporaryError` (LianaAutomation answered 5xx or timed out,
or the mail server is down), the connector publishes the message to
`survey.liana-events` again after `retry.backoff_seconds(attempt)`: 2, 4, 8, ...
seconds, at most 300. The attempt number travels in the `x-attempt` header. The
original message is acknowledged only after the copy is published, so a crash in
between redelivers it instead of losing it. The sync log row stays `retrying`
and is reused by each attempt.

After `retry.MAX_ATTEMPTS` (8) the message goes to `survey.dead-letter`, and the
port's `give_up()` turns the `retrying` row into `failed` ("Gave up after several
tries. Last error: …"), so the admin sees Retry instead of a row that waits
forever. Any other error is not retried: the message goes to the dead-letter
queue at once. The local gateway without RabbitMQ does not retry.

## Switching adapters
`LIANA_ADAPTER=mock` (default) or `LIANA_ADAPTER=lianaautomation` in `.env`. The
LianaAutomation credentials are not in `.env`: each organisation saves its own on the
Integrations page, encrypted with `INTEGRATION_SECRET_KEY`.

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
