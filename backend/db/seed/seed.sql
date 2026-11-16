-- Demo data only. No real people. Safe to run more than once.
-- Runs as the schema owner, so it sets app.tenant_id to pass row-level security.

begin;

select set_config('app.tenant_id', '00000000-0000-4000-8000-000000000001', true);

insert into tenants (id, name) values
  ('00000000-0000-4000-8000-000000000001', 'Example Members Association')
on conflict (id) do nothing;

insert into users (id, tenant_id, name, email) values
  ('00000000-0000-4000-8000-000000000101', '00000000-0000-4000-8000-000000000001',
   'Anna Virtanen', 'anna.virtanen@example.org')
on conflict (id) do nothing;

insert into surveys (id, tenant_id, title, type, status, created_by) values
  ('00000000-0000-4000-8000-000000000201', '00000000-0000-4000-8000-000000000001',
   'Member satisfaction 2026', 'nps', 'draft', '00000000-0000-4000-8000-000000000101')
on conflict (id) do nothing;

insert into questions (tenant_id, survey_id, position, kind, prompt) values
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000201', 1, 'nps',
   'How likely are you to recommend Example Members Association to a friend?'),
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000201', 2, 'text',
   'What is the main reason for your score?')
on conflict (survey_id, position) do nothing;

commit;

-- Built-in templates are product content and come from the migrations
-- (20261117090000_templates_and_thank_you.sql), not from this demo seed.

