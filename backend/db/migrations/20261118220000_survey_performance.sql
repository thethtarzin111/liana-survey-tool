-- migrate:up
create type distribution_channel as enum ('email', 'link', 'qr');

alter table responses
  add column channel distribution_channel not null default 'link';

create table survey_channel_views (
  survey_id uuid not null references surveys(id) on delete cascade,
  tenant_id uuid not null references tenants(id) on delete cascade,
  channel distribution_channel not null,
  view_count integer not null default 0 check (view_count >= 0),
  updated_at timestamptz not null default now(),
  primary key (survey_id, channel)
);

alter table survey_channel_views enable row level security;
alter table survey_channel_views force row level security;
create policy tenant_isolation on survey_channel_views
  using (tenant_id = app_tenant_id()) with check (tenant_id = app_tenant_id());

-- migrate:down
drop table if exists survey_channel_views;
alter table responses drop column channel;
drop type distribution_channel;
