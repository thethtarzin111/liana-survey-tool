# 0003 Dev-auth stub, no login screen

**Status:** accepted · 2026-11-15

## Context
Login is out of scope for this implementation. In production, users would sign
in through Liana's existing account system, which the team cannot access.

## Decision
`services/api/survey_api/auth/dev_stub.py` treats every request as the demo
user from `.env` (`AUTH_MODE=dev`): Anna Virtanen, Example Members Association.

## Consequences
- `tenant_id` and row-level security work exactly as they will in production.
- Liana replaces one function, `current_user()`, with one that reads their
  session or token. The rest of the code does not change.
- Never deploy with `AUTH_MODE=dev` anywhere public with real data.
