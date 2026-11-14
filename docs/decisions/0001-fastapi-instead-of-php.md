# 0001 FastAPI instead of PHP

**Status:** accepted · 2026-11-15

## Context
Liana's preferred stack is React, PHP and PostgreSQL. Liana said teams may
choose other technologies with a justification. The team has no access to
Liana's codebase, so code cannot be merged into Liana's products directly.

## Decision
Backend in Python 3.12 with FastAPI. Frontend in React + TypeScript and the
database in PostgreSQL, as Liana prefers.

## Why
- The team knows Python well, so it can deliver a working, tested backend in
  the course time.
- FastAPI produces the OpenAPI description automatically, which is the
  contract Liana keeps whatever language they use.
- Without Liana's codebase, PHP code from us would still need reworking to fit
  Liana's framework, libraries and conventions.

## Consequences
- If Liana runs the backend as its own service, nothing needs rewriting.
- If Liana rebuilds it in PHP, the frontend, database schema, API contract,
  tests and docs are reused; only the backend code is rewritten.
- To keep that rewrite small: plain SQL migrations, business rules in plain
  modules (`domain.py`), and tests that run against HTTP. See `docs/handoff.md`.
