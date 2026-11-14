# Data model (draft)

Defined in `db/migrations/20261115000000_initial_schema.sql`. Every table has
`tenant_id` with row-level security; built-in templates have `tenant_id = null`
and are visible to everyone.

| Table | What | Notes |
|---|---|---|
| `tenants` | A Liana customer organisation | |
| `users` | Marketers in a tenant | Dev stub: one demo user |
| `surveys` | One survey | type `nps/csat/poll/custom`; status `draft/scheduled/live/closed`; `anonymous` defaults to true; language `fi/sv/en`; optional open/close dates and response limit |
| `questions` | Questions of a survey, ordered by `position` | kind `nps/rating/single_choice/multiple_choice/text`; `options` is JSON |
| `responses` | One submitted response | `link_token_hash` stops double counting; `contact_ref` only in identified mode |
| `answers` | One answer to one question | number, text or choices |
| `contact_requests` | "Contact me" requests | status `new/contacted/done` |
| `survey_aggregates` | Totals kept by the worker | response count, score distribution |
| `templates` | Ready-made surveys | `tenant_id` null = built-in |

## Open questions
- Response rate needs the number of recipients. Does that come from LianaMailer
  (API) or does the marketer type it in?
- Data retention period for answers (see `gdpr.md`).
