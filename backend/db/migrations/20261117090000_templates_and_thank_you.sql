-- migrate:up

-- Thumbs rating: the fixed "Not for me / Good / Loved it" scale (answers 0, 1, 2).
alter type question_kind add value if not exists 'thumbs';

-- The message readers see after answering, edited on "Edit and preview".
alter table surveys add column thank_you text;

alter table templates
  add column thank_you text not null default '',
  -- Order on the Templates page and in "Pick a template".
  add column sort_order integer not null default 0,
  -- Shown as a card on the Templates page (the prototype shows five).
  add column featured boolean not null default false;

-- Replace the scaffold's placeholder templates with the prototype's built-in ones.
-- Runs as the schema owner, like the seed (built-in rows have tenant_id null).
-- {organisation} is replaced with the organisation's name when a survey is created.
delete from templates where id in (
  '00000000-0000-4000-8000-000000000301',
  '00000000-0000-4000-8000-000000000302',
  '00000000-0000-4000-8000-000000000303'
);

insert into templates (id, tenant_id, name, type, description, thank_you, sort_order, featured, questions) values
  ('00000000-0000-4000-8000-000000000311', null, 'Newsletter feedback', 'thumbs',
   'One tap at the end of a newsletter',
   'Thanks! Your answer helps us make the next newsletter better.', 1, true,
   '[{"kind":"thumbs","prompt":"How was this newsletter?","required":true},
     {"kind":"reasons","prompt":"","options":["Not relevant to me","Too long","Too often","Something else"],"required":false}]'),
  ('00000000-0000-4000-8000-000000000312', null, 'Member NPS', 'nps',
   'Yearly loyalty check for members',
   'Thank you. This takes our member work forward.', 2, true,
   '[{"kind":"nps","prompt":"How likely are you to recommend {organisation} to a friend or colleague?","required":true},
     {"kind":"reasons","prompt":"","options":["Events and activities","Hard to find information","Membership fee","Something else"],"required":false}]'),
  ('00000000-0000-4000-8000-000000000313', null, 'Event feedback', 'thumbs',
   'After a webinar or member event',
   'Thanks for coming and for telling us what you thought.', 3, true,
   '[{"kind":"thumbs","prompt":"How was the event?","required":true},
     {"kind":"reasons","prompt":"","options":["Not relevant to me","Too long","Poor timing","Something else"],"required":false}]'),
  ('00000000-0000-4000-8000-000000000314', null, 'Course satisfaction', 'csat',
   'Satisfaction after a course',
   'Thank you! We use your answers to plan the next course.', 4, true,
   '[{"kind":"rating","prompt":"How satisfied were you with the course?","required":true},
     {"kind":"reasons","prompt":"","options":["Pace","Venue","Practice time","Something else"],"required":false}]'),
  ('00000000-0000-4000-8000-000000000315', null, 'Quick poll', 'custom',
   'One multiple-choice question for a fast vote',
   '', 5, true,
   '[{"kind":"single_choice","prompt":"Which topic should our next event cover?","options":["Volunteering","Fundraising","Digital tools","Something else"],"required":true}]'),
  ('00000000-0000-4000-8000-000000000316', null, 'Course feedback', 'thumbs',
   'After a course or training session',
   'Thanks! We read every answer before planning the next course.', 6, false,
   '[{"kind":"thumbs","prompt":"How was the course?","required":true},
     {"kind":"reasons","prompt":"","options":["Too difficult","Too easy","Too fast","Something else"],"required":false}]'),
  ('00000000-0000-4000-8000-000000000317', null, 'Employee NPS (eNPS)', 'nps',
   'Anonymous pulse for your team',
   'Thank you. Answers are anonymous and shared with the team.', 7, false,
   '[{"kind":"nps","prompt":"How likely are you to recommend working here to a friend?","required":true},
     {"kind":"reasons","prompt":"","options":["Workload","Management","Pay and benefits","Something else"],"required":false}]'),
  ('00000000-0000-4000-8000-000000000318', null, 'Event satisfaction', 'csat',
   'Satisfaction after an event',
   'Thank you! See you at the next event.', 8, false,
   '[{"kind":"rating","prompt":"How satisfied were you with the event?","required":true},
     {"kind":"reasons","prompt":"","options":["Programme","Venue","Food and drink","Something else"],"required":false}]')
on conflict (id) do nothing;

-- migrate:down

delete from templates where id between '00000000-0000-4000-8000-000000000311'
                                  and '00000000-0000-4000-8000-000000000318';
alter table templates drop column featured, drop column sort_order, drop column thank_you;
alter table surveys drop column thank_you;
-- Postgres cannot drop an enum value; rebuild question_kind without 'thumbs'.
-- Thumbs questions become 3-point single choice questions.
alter table questions alter column kind type text;
update questions set kind = 'single_choice', options = '["Not for me","Good","Loved it"]'::jsonb
where kind = 'thumbs';
drop type question_kind;
create type question_kind as enum (
  'nps', 'rating', 'single_choice', 'multiple_choice', 'text', 'dropdown', 'long_text', 'reasons'
);
alter table questions alter column kind type question_kind using kind::question_kind;
