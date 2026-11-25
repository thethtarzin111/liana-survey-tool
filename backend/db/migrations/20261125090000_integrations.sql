-- migrate:up

-- One connection per organisation and Liana product (the Integrations page).
-- The client secret is encrypted by the Liana connector before it is stored
-- (INTEGRATION_SECRET_KEY); the database never sees it in plain text.
create table integrations (
  id               uuid primary key default gen_random_uuid(),
  tenant_id        uuid not null references tenants(id) on delete cascade,
  provider         text not null check (provider in ('liana_automation')),
  host             text not null,
  auth_type        text not null default 'oauth' check (auth_type in ('oauth')),
  client_id        text not null,
  secret_encrypted bytea not null,
  -- The last 4 characters of the secret, so the page can show "••••a91f".
  secret_hint      text not null,
  channel_id       text,
  channel_name     text,
  -- What to send: {"answers": bool, "contact_requests": bool, "themes": bool}.
  settings         jsonb not null default '{}',
  -- disconnected: saved, not tested yet; connected: last test passed;
  -- error: last test or call failed (see last_error).
  status           text not null default 'disconnected'
                   check (status in ('disconnected', 'connected', 'error')),
  last_error       text,
  updated_at       timestamptz not null default now(),
  unique (tenant_id, provider)
);

alter table integrations enable row level security;
alter table integrations force row level security;
create policy tenant_isolation on integrations
  using (tenant_id = app_tenant_id()) with check (tenant_id = app_tenant_id());

-- Every event sent to (or meant for) Liana: the sync log on the Integrations
-- page, and later the outbox the worker fills in the answer's transaction.
-- response_id is null for test events.
create table integration_events (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null references tenants(id) on delete cascade,
  provider     text not null default 'liana_automation',
  response_id  uuid references responses(id) on delete set null,
  verb         text not null,
  -- The event as sent to POST /import (contact identity included), so a retry
  -- sends exactly the same data.
  payload      jsonb not null,
  test         boolean not null default false,
  status       text not null default 'pending'
               check (status in ('pending', 'sent', 'retrying', 'failed')),
  attempts     integer not null default 0 check (attempts >= 0),
  last_error   text,
  created_at   timestamptz not null default now(),
  sent_at      timestamptz
);

create index integration_events_log on integration_events (tenant_id, created_at desc);

alter table integration_events enable row level security;
alter table integration_events force row level security;
create policy tenant_isolation on integration_events
  using (tenant_id = app_tenant_id()) with check (tenant_id = app_tenant_id());

-- migrate:down

drop table integration_events;
drop table integrations;
