-- migrate:up

-- An organisation's own templates keep the branding colours of the survey they
-- were saved from, and surveys made from them start with those colours.
-- Built-in templates have none: their surveys get the survey defaults.
alter table templates
  add column accent_color text check (accent_color ~ '^#[0-9A-F]{6}$'),
  add column background_color text check (background_color ~ '^#[0-9A-F]{6}$');

-- migrate:down

alter table templates
  drop column background_color,
  drop column accent_color;
