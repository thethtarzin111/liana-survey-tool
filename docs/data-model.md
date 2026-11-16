# Data model (draft)

Defined in `backend/db/migrations/20261115000000_initial_schema.sql`. Every table has
`tenant_id` with row-level security; built-in templates have `tenant_id = null`
and are visible to everyone.

| Table | What | Notes |
|---|---|---|
| `tenants` | A Liana customer organisation | |
| `users` | Marketers in a tenant | Dev stub: one demo user |
| `surveys` | One survey | required title (1–200 characters); optional description (up to 1000 characters); optional thank-you message (up to 500); reader options `comment_field`, `show_results`, `contact_opt_in` (all default true); type `thumbs/nps/csat/custom` (custom = start from scratch); status `draft/scheduled/live/closed`; `anonymous` defaults to true; language `fi/sv/en`; optional open/close dates and response limit |
| `questions` | Questions of a survey, ordered by `position` | kind `single_choice/multiple_choice/dropdown/text/long_text/rating/nps/reasons` (rules in `survey_manager/questions/domain.py`); `options` is a JSON list of texts, only for the four choice kinds |
| `responses` | One submitted response | `link_token_hash` stops double counting; `contact_ref` only in identified mode |
| `answers` | One answer to one question | number, text or choices |
| `contact_requests` | "Contact me" requests | status `new/contacted/done` |
| `survey_aggregates` | Totals kept by the worker | response count, score distribution |
| `templates` | Ready-made surveys | `tenant_id` null = built-in (from migration `20261117090000`); `questions` JSON list, `thank_you`, `sort_order`, `featured` (Templates page card); `{organisation}` in text becomes the organisation's name |

## Open questions
- Response rate needs the number of recipients. Does that come from LianaMailer
  (API) or does the marketer type it in?
- Data retention period for answers (see `gdpr.md`).
