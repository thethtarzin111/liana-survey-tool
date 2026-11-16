-- migrate:up

-- The prototype's "Answer type" list has eight types. Add the three missing ones:
-- Dropdown, Paragraph (long_text) and Reason bubbles. "text" stays Short answer.
alter type question_kind add value if not exists 'dropdown';
alter type question_kind add value if not exists 'long_text';
alter type question_kind add value if not exists 'reasons';

-- Options are now only for choice types, and always text. Bring existing rows in line.
update questions set options = '[]'::jsonb
where kind in ('nps', 'rating', 'text') and options <> '[]'::jsonb;

update questions
set options = (select coalesce(jsonb_agg(to_jsonb(item #>> '{}')), '[]'::jsonb)
               from jsonb_array_elements(options) as item)
where kind in ('single_choice', 'multiple_choice')
  and exists (select 1 from jsonb_array_elements(options) as item
              where jsonb_typeof(item) <> 'string');

-- migrate:down

-- Postgres cannot drop enum values, so rebuild the type. Questions of the new
-- types fall back to the closest old one.
alter table questions alter column kind type text;
update questions set kind = case kind
  when 'dropdown' then 'single_choice'
  when 'long_text' then 'text'
  when 'reasons' then 'multiple_choice'
  else kind end;
drop type question_kind;
create type question_kind as enum ('nps', 'rating', 'single_choice', 'multiple_choice', 'text');
alter table questions alter column kind type question_kind using kind::question_kind;
