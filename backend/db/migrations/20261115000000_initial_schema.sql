-- migrate:up
-- Initial LianaSurvey schema (draft; see docs/data-model.md).
-- Plain SQL on purpose: any language can run these files (we use dbmate).
--
-- Tenant isolation: every table has tenant_id, and row-level security only
-- shows rows where tenant_id = current_setting('app.tenant_id').
-- The services connect as the app role (survey_app), which is not the table
-- owner, so these policies always apply.

create extension if not exists pgcrypto;

create table tenants (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  created_at  timestamptz not null default now()
);

create table users (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  name        text not null,
  email       text not null,
  created_at  timestamptz not null default now(),
  unique (tenant_id, email)
);

create type survey_type as enum ('nps', 'csat', 'poll', 'custom');
create type survey_status as enum ('draft', 'scheduled', 'live', 'closed');

create table surveys (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references tenants(id) on delete cascade,
  title         text not null,
  type          survey_type not null,
  status        survey_status not null default 'draft',
  -- Anonymous by default (R05). Identified only after respondent opt-in.
  anonymous     boolean not null default true,
  language      text not null default 'en' check (language in ('fi', 'sv', 'en')),
  opens_at      timestamptz,
  closes_at     timestamptz,
  response_limit integer check (response_limit > 0),
  created_by    uuid references users(id) on delete set null,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create type question_kind as enum ('nps', 'rating', 'single_choice', 'multiple_choice', 'text');

create table questions (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  survey_id   uuid not null references surveys(id) on delete cascade,
  position    integer not null,
  kind        question_kind not null,
  prompt      text not null,
  options     jsonb not null default '[]'::jsonb,
  required    boolean not null default true,
  unique (survey_id, position)
);

create table responses (
  id               uuid primary key default gen_random_uuid(),
  tenant_id        uuid not null references tenants(id) on delete cascade,
  survey_id        uuid not null references surveys(id) on delete cascade,
  submitted_at     timestamptz not null default now(),
  -- Hash of the signed single-use link token; stops double counting.
  link_token_hash  text not null,
  -- LianaMailer contact id, only in identified mode. No e-mail addresses here.
  contact_ref      text,
  unique (survey_id, link_token_hash)
);

create table answers (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null references tenants(id) on delete cascade,
  response_id  uuid not null references responses(id) on delete cascade,
  question_id  uuid not null references questions(id) on delete cascade,
  value_number numeric,
  value_text   text,
  value_choices jsonb
);

create type contact_request_status as enum ('new', 'contacted', 'done');

create table contact_requests (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null references tenants(id) on delete cascade,
  survey_id    uuid not null references surveys(id) on delete cascade,
  response_id  uuid not null references responses(id) on delete cascade,
  contact_ref  text not null,
  status       contact_request_status not null default 'new',
  created_at   timestamptz not null default now()
);

-- Totals kept up to date by the worker, so results pages stay fast (R04).
create table survey_aggregates (
  survey_id       uuid primary key references surveys(id) on delete cascade,
  tenant_id       uuid not null references tenants(id) on delete cascade,
  response_count  integer not null default 0,
  -- e.g. {"0": 3, "9": 12} for NPS, {"1": 2, "5": 40} for CSAT
  distribution    jsonb not null default '{}'::jsonb,
  updated_at      timestamptz not null default now()
);

-- Templates: tenant_id null = built-in template visible to every tenant.
create table templates (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid references tenants(id) on delete cascade,
  name        text not null,
  type        survey_type not null,
  description text not null default '',
  questions   jsonb not null default '[]'::jsonb
);

create index on surveys (tenant_id, status);
create index on questions (survey_id);
create index on responses (survey_id, submitted_at);
create index on answers (response_id);
create index on contact_requests (tenant_id, status);

-- Row-level security ------------------------------------------------------
create function app_tenant_id() returns uuid
  language sql stable
  as $$ select nullif(current_setting('app.tenant_id', true), '')::uuid $$;

alter table tenants enable row level security;
alter table tenants force row level security;
create policy tenant_isolation on tenants using (id = app_tenant_id());

alter table templates enable row level security;
alter table templates force row level security;
create policy tenant_isolation on templates
  using (tenant_id is null or tenant_id = app_tenant_id())
  with check (tenant_id = app_tenant_id());

do $$
declare t text;
begin
  foreach t in array array['users', 'surveys', 'questions', 'responses', 'answers',
                           'contact_requests', 'survey_aggregates']
  loop
    execute format('alter table %I enable row level security', t);
    execute format('alter table %I force row level security', t);
    execute format(
      'create policy tenant_isolation on %I using (tenant_id = app_tenant_id()) '
      'with check (tenant_id = app_tenant_id())', t);
  end loop;
end $$;

-- The app role and its table permissions come from infra/postgres/init
-- (default privileges), so this file does not name the role.

-- migrate:down
drop table if exists templates, survey_aggregates, contact_requests, answers, responses,
  questions, surveys, users, tenants cascade;
drop function if exists app_tenant_id();
drop type if exists contact_request_status, question_kind, survey_status, survey_type;
