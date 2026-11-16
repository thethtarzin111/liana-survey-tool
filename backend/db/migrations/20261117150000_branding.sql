-- migrate:up

-- Branding per survey, shown on the pages respondents see. Defaults match the
-- prototype: accent "Teal" and a white background.
alter table surveys
  add column accent_color text not null default '#0F6A5E'
    check (accent_color ~ '^#[0-9A-F]{6}$'),
  add column background_color text not null default '#FFFFFF'
    check (background_color ~ '^#[0-9A-F]{6}$'),
  -- Set when a logo is uploaded; used to build the logo URL (and to bust caches).
  add column logo_updated_at timestamptz;

-- The logo itself (at most 1 MB, PNG, JPEG, SVG or WebP; checked by survey-manager).
-- Kept in the database so the demo needs no file storage.
create table survey_logos (
  survey_id     uuid primary key references surveys(id) on delete cascade,
  tenant_id     uuid not null references tenants(id) on delete cascade,
  content_type  text not null
    check (content_type in ('image/png', 'image/jpeg', 'image/svg+xml', 'image/webp')),
  data          bytea not null check (octet_length(data) between 1 and 1048576),
  updated_at    timestamptz not null default now()
);

alter table survey_logos enable row level security;
alter table survey_logos force row level security;
create policy tenant_isolation on survey_logos
  using (tenant_id = app_tenant_id()) with check (tenant_id = app_tenant_id());

-- migrate:down

drop table survey_logos;
alter table surveys
  drop column logo_updated_at,
  drop column background_color,
  drop column accent_color;
