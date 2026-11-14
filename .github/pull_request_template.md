## What
<!-- One or two sentences. -->

## Backlog card
<!-- Link to the Trello card. -->

## How to check it
<!-- Steps a reviewer can follow, e.g. "docker compose up, open /results". -->

## Checklist
- [ ] Only this card's scope
- [ ] `make lint` and `make test` pass
- [ ] `docs/api/openapi.yaml` updated (if endpoints changed)
- [ ] New tables have `tenant_id`, an RLS policy and a check in `db/tests/rls_check.sql`
- [ ] No real personal data, no secrets, no staging logins
- [ ] Screenshots at 1440px for UI changes
