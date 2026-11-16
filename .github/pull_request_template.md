## What
<!-- One or two sentences. -->

## Issue
Closes #<!-- issue number -->

## How to check it
<!-- Steps a reviewer can follow, e.g. "npm run dev, open /results". -->

## Checklist
- [ ] Only this issue's scope
- [ ] `make lint` and `make test` pass
- [ ] `docs/api/openapi.yaml` updated (if endpoints changed)
- [ ] New tables have `tenant_id`, an RLS policy and a check in `backend/db/tests/rls_check.sql`
- [ ] No real personal data, no secrets, no staging logins
- [ ] Screenshots at 1440px for UI changes
