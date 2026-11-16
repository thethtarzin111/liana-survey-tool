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

-- Built-in templates (tenant_id null). The with-check policy blocks this for
-- normal roles; it works because seeding runs as the Postgres superuser that
-- owns the schema (POSTGRES_USER). On a managed database, run it as a role
-- with BYPASSRLS.
begin;
insert into templates (id, tenant_id, name, type, description, questions) values
  ('00000000-0000-4000-8000-000000000301', null, 'Net Promoter Score', 'nps',
   'One 0–10 question plus an optional comment.',
   '[{"kind":"nps","prompt":"How likely are you to recommend us to a friend?"},{"kind":"text","prompt":"What is the main reason for your score?","required":false}]'),
  ('00000000-0000-4000-8000-000000000302', null, 'Customer satisfaction', 'csat',
   'A 1–5 rating for one service or event.',
   '[{"kind":"rating","prompt":"How satisfied were you?","options":[1,2,3,4,5]}]'),
  ('00000000-0000-4000-8000-000000000303', null, 'Post-event feedback', 'custom',
   'Rating, best part and what to improve.',
   '[{"kind":"rating","prompt":"How was the event?","options":[1,2,3,4,5]},{"kind":"text","prompt":"What did you like most?","required":false}]')
on conflict (id) do nothing;
commit;
