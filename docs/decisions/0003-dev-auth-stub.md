# 0003 Dev-auth stub, no login screen

> Runtime update: see [0005 Native development](0005-native-development.md).
> Container and nginx references below describe the former deployment.

**Status:** accepted · 2026-11-15

## Context
Login is out of scope for this implementation. In production, users would sign
in through Liana's existing account system, which the team cannot access.

## Decision
Every admin request is the demo user from `.env` (`AUTH_MODE=dev`): Anna
Virtanen, Example Members Association. The API gateway (`backend/services/gateway`)
sets this user on each request and answers `/api/v1/me`; the services read it
with `liana_survey_shared.web.auth.current_user()` (see decision 0004).

## Consequences
- `tenant_id` and row-level security work exactly as they will in production.
- Liana plugs their login into the gateway (nginx `auth_request` against
  their session or token) and maps the user into the same headers. The
  services do not change.
- Never deploy with `AUTH_MODE=dev` anywhere public with real data.
