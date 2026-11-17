-- migrate:up

-- Which organisation a public link belongs to (#42). Readers have no login, so
-- the respondent service first looks up the token here, then reads the survey
-- through tenant_connection() with row-level security as usual. A token is a
-- random 128-bit secret, so being able to look one up reveals nothing new.
create table survey_links (
  link_token  text primary key,
  survey_id   uuid not null unique references surveys(id) on delete cascade,
  tenant_id   uuid not null references tenants(id) on delete cascade
);

alter table survey_links enable row level security;
alter table survey_links force row level security;
-- Anyone may look a token up; only the survey's own organisation may add one.
create policy lookup_by_token on survey_links for select using (true);
create policy own_tenant_writes on survey_links for insert
  with check (tenant_id = app_tenant_id());
create policy own_tenant_deletes on survey_links for delete
  using (tenant_id = app_tenant_id());

-- Surveys published before this migration.
insert into survey_links (link_token, survey_id, tenant_id)
select link_token, id, tenant_id from surveys where link_token is not null
on conflict do nothing;

-- migrate:down

drop table survey_links;
