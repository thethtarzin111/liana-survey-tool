# Instructions for coding agents (Claude Code)

Read `README.md` and `docs/architecture.md` first.

## How to work
- Work on one issue at a time, on its own branch (`feat/<short-name>`).
  Open a pull request; never commit to or merge into `main`.
- Before you say an issue is done, run `make lint` and `make test` (or the commands
  inside the Makefile on Windows) and report the real output.
- Keep changes inside the issue's scope. Write down anything else you notice in
  the PR description instead of fixing it.

## Stack and rules
- Frontend: React 18 + TypeScript + Vite in `frontend`. One folder per
  sidebar item in `src/features/`. Use the CSS variables in
  `src/styles/tokens.css`; do not hard-code colours or font sizes.
- Backend: Python 3.12, FastAPI, PostgreSQL, RabbitMQ. Separate services behind
  an API gateway, as in the mid-term report (`docs/architecture.md`, decision 0004).
  - Put code in the service that owns it (survey-manager, respondent,
    data-analyzer, worker, liana-connector). Services never import each other;
    shared code goes in `backend/packages/shared-py`. New route prefixes also need routing
    in `backend/scripts/local_gateway.py`.
  - In each service area keep three layers: `domain.py` (plain Python rules),
    `repo.py` (SQL), `routes.py` (HTTP). Business rules never live in routes.
    This keeps a later PHP port simple (`docs/handoff.md`).
  - Get the user with `liana_survey_shared.web.auth.current_user()` (set by the
    gateway) and the database with `liana_survey_shared.web.db.tenant_db()`:
    `with db() as conn:` inside the handler, so the commit happens before the
    response is sent (never yield a connection from a dependency).
  - Every database call goes through `liana_survey_shared.db.tenant_connection()`.
    Every new table gets `tenant_id` plus a row-level security policy, and
    `backend/db/tests/rls_check.sql` gets a check for it.
  - Migrations are plain `.sql` files in `backend/db/migrations` (dbmate format:
    `-- migrate:up` / `-- migrate:down`). Never edit a migration that is on `main`;
    add a new one.
  - Queue message formats live in `liana_survey_shared/messages.py`. Changing
    one means updating `docs/integrations.md`.
- API: update `docs/api/openapi.yaml` in the same PR as any endpoint change.
- Only `backend/services/liana-connector` talks to Liana products, through a port in
  `ports/` and an adapter in `adapters/`. `mock` is the default adapter.

## Privacy (GDPR)
- Answers are anonymous by default. Store a contact reference only in
  identified mode after opt-in. Never store recipient e-mail addresses.
- Use demo data only (Example Members Association, Anna Virtanen). No real
  people, no real Liana customer data, no staging logins in the repo.

## Out of scope (for now)
- Login screens and real authentication: use the dev-auth stub.
- The design system page and the respondent screens from the prototype.
  The respondent side is only a minimal endpoint that records an answer and
  returns a plain thank-you page.

## Reference
- Prototype snapshot: `design/prototype/` (open the Claude Design artifact for
  the clickable version). Rebuild screens in React; never copy its code.
- Backlog: GitHub Project "survey-tool-backlog" (https://github.com/users/thethtarzin111/projects/1). Acceptance criteria are on each issue.
