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

-- ---------------------------------------------------------------------------
-- Results redesign demo data: four surveys with responses from
-- September to November 2026. Everything is derived from fixed keys with
-- generate_series, so a second run inserts nothing new.
-- Segments: Member NPS 2026 has members, volunteers and untagged answers of 5
-- or more, plus 4 'partners' and 3 'board' answers. Both are under 5, so they
-- are grouped as Other (7 answers, shown). Student services moves its untagged
-- answers into 'members', so every group has 5 or more. Segments are therefore
-- on for both surveys.
-- ---------------------------------------------------------------------------

insert into surveys (id, tenant_id, title, type, status, created_by, created_at, opens_at,
                     closes_at, published_at, link_token) values
  ('00000000-0000-4000-8000-000000000211', '00000000-0000-4000-8000-000000000001',
   'May newsletter', 'thumbs', 'live', '00000000-0000-4000-8000-000000000101',
   '2026-08-25 09:00+03', '2026-09-01 09:00+03', null, '2026-09-01 09:00+03',
   'demo-may-newsletter-0211'),
  ('00000000-0000-4000-8000-000000000212', '00000000-0000-4000-8000-000000000001',
   'Member NPS 2026', 'nps', 'live', '00000000-0000-4000-8000-000000000101',
   '2026-08-25 09:30+03', '2026-09-01 09:00+03', null, '2026-09-01 09:00+03',
   'demo-member-nps-2026-0212'),
  ('00000000-0000-4000-8000-000000000213', '00000000-0000-4000-8000-000000000001',
   'Spring course feedback', 'csat', 'closed', '00000000-0000-4000-8000-000000000101',
   '2026-08-25 10:00+03', '2026-09-01 09:00+03', '2026-11-17 18:00+02', '2026-09-01 09:00+03',
   'demo-spring-course-0213'),
  ('00000000-0000-4000-8000-000000000214', '00000000-0000-4000-8000-000000000001',
   'Student services survey', 'custom', 'live', '00000000-0000-4000-8000-000000000101',
   '2026-08-25 10:30+03', '2026-09-01 09:00+03', null, '2026-09-01 09:00+03',
   'demo-student-services-0214')
on conflict (id) do nothing;

insert into survey_links (link_token, survey_id, tenant_id)
select link_token, id, tenant_id from surveys
where id in ('00000000-0000-4000-8000-000000000211', '00000000-0000-4000-8000-000000000212',
             '00000000-0000-4000-8000-000000000213', '00000000-0000-4000-8000-000000000214')
on conflict do nothing;

insert into questions (tenant_id, survey_id, position, kind, prompt, options) values
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000211', 1, 'thumbs',
   'How was this newsletter?', '[]'),
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000211', 2, 'reasons',
   'What stood out?',
   '["Clear writing","Useful news","Too long","Good pictures","Not relevant to me"]'),
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000211', 3, 'text',
   'Anything you would change?', '[]'),
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000212', 1, 'nps',
   'How likely are you to recommend Example Members Association to a friend?', '[]'),
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000212', 2, 'reasons',
   'What shaped your score?',
   '["Events","Member benefits","Communication","Price","Community"]'),
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000212', 3, 'text',
   'Anything else you want to tell us?', '[]'),
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000213', 1, 'rating',
   'How satisfied were you with the course?', '[]'),
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000213', 2, 'reasons',
   'What did you value most?',
   '["Teacher","Content","Schedule","Materials","Group size"]'),
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000213', 3, 'text',
   'Any other comments?', '[]'),
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000214', 1,
   'multiple_choice', 'Which services have you used?',
   '["Counselling","Housing help","Career services","Study groups","IT support"]'),
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000214', 2, 'rating',
   'How easy was it to get help?', '[]'),
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000214', 3, 'dropdown',
   'Which campus are you on?', '["Central","North","Online"]'),
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000214', 4, 'long_text',
   'How could we improve student services?', '[]')
on conflict (survey_id, position) do nothing;

-- Plan: how many responses each survey gets and its pool of comments.
create temp table seed_surveys on commit drop as
select * from (values
  ('00000000-0000-4000-8000-000000000211'::uuid, 'newsletter', 1, 40, false, array[
    'Short and to the point, thanks.',
    'I liked the photos from the autumn fair.',
    'The member stories are my favourite part.',
    'A bit too long for a phone screen.',
    'Please add the event dates near the top.',
    'More news about the volunteer evenings, please.',
    'Nothing to change, keep it up.',
    'The layout was hard to read on my phone.']),
  ('00000000-0000-4000-8000-000000000212'::uuid, 'nps', 2, 40, true, array[
    'The autumn events were well organised.',
    'Membership price went up and I am not sure it is worth it.',
    'Friendly community, easy to get involved.',
    'I would like clearer news about benefits.',
    'The volunteer coordinator was very helpful.',
    'Hard to find information on the website.',
    'Great atmosphere at the meetups.',
    'Fewer emails, please, but keep the monthly summary.']),
  ('00000000-0000-4000-8000-000000000213'::uuid, 'course', 3, 40, false, array[
    'The teacher explained everything clearly.',
    'Course materials arrived late.',
    'Good pace and a nice small group.',
    'I wanted more practical exercises.',
    'The evening schedule suited me well.',
    'The room was too warm.',
    'Would join a follow-up course.',
    'Content was good but the slides were dense.']),
  ('00000000-0000-4000-8000-000000000214'::uuid, 'services', 4, 30, false, array[
    'Counselling appointments are hard to book in the evening.',
    'IT support fixed my login problem in a day.',
    'More study group spaces on the north campus, please.',
    'The housing guide was very useful.',
    'Online services work well, in-person queues are long.',
    'Career services helped me with my CV.'])
) as t(survey_id, slug, idx, n, has_partners, comments);

create temp table seed_resp on commit drop as
select b.*,
  case b.slug
    when 'newsletter' then case when b.q < 20 then 0 when b.q < 65 then 1 else 2 end
    when 'nps' then (array[0,3,5,6,6,7,7,8,8,9,9,9,10,10,10,10])[1 + least(15, b.q * 16 / 125)]
    else case when b.q < 10 then 1 when b.q < 25 then 2 when b.q < 45 then 3
              when b.q < 75 then 4 else 5 end
  end as score
from (
  select s.survey_id, s.slug, s.idx, s.n, s.comments, g as i,
    md5('resp-' || s.slug || '-' || g)::uuid as id,
    md5('link-' || s.slug || '-' || g) as link_token_hash,
    r.submitted_at,
    case when s.has_partners and g > s.n + 4 then 'board'
         when s.has_partners and g > s.n then 'partners'
         when s.slug = 'services' and g % 8 = 7 then 'members'
         else (array['members','members','members','members','members',
                     'volunteers','volunteers','all'])[1 + g % 8] end as segment,
    (array['email','link','qr','email','link','email'])[1 + g % 6] as channel,
    ((g * 47 + s.idx * 13) % 100)
      + 8 * (extract(month from r.submitted_at at time zone 'Europe/Helsinki')::int - 9)
      + case when g % 8 in (5, 6) then 6 else 0 end as q,
    case when g in (3, 9, 15) or (s.slug = 'nps' and g in (21, 27, 33))
         then 'C-' || (1000 + s.idx * 100 + g) end as contact_ref
  from seed_surveys s
  cross join lateral generate_series(1, s.n + case when s.has_partners then 7 else 0 end) g
  cross join lateral (
    select (('2026-09-02 09:00'::timestamp
             + floor((g - 1) * 76.0 / (s.n + case when s.has_partners then 7 else 0 end))
               * interval '1 day'
             + ((g * 37) % 9) * interval '1 hour') at time zone 'Europe/Helsinki') as submitted_at
  ) r
) b;

insert into responses (id, tenant_id, survey_id, submitted_at, link_token_hash, contact_ref,
                       channel, segment)
select id, '00000000-0000-4000-8000-000000000001', survey_id, submitted_at, link_token_hash,
       contact_ref, channel::distribution_channel, segment
from seed_resp
on conflict (survey_id, link_token_hash) do update set segment = excluded.segment;

-- Question 1 (score) of the three standard surveys and the rating of the custom one.
insert into answers (tenant_id, response_id, question_id, value_number)
select '00000000-0000-4000-8000-000000000001', r.id, q.id, r.score
from seed_resp r
join questions q on q.survey_id = r.survey_id
  and q.position = case when r.slug = 'services' then 2 else 1 end
where not exists (select 1 from answers a where a.response_id = r.id and a.question_id = q.id);

-- Reasons (standard surveys): one or two options.
insert into answers (tenant_id, response_id, question_id, value_choices)
select '00000000-0000-4000-8000-000000000001', r.id, q.id,
  case when r.i % 3 = 0
       then jsonb_build_array(q.options ->> ((r.i * 3) % 5), q.options ->> ((r.i * 3 + 2) % 5))
       else jsonb_build_array(q.options ->> ((r.i * 3) % 5)) end
from seed_resp r
join questions q on q.survey_id = r.survey_id and q.position = 2
where r.slug <> 'services'
  and not exists (select 1 from answers a where a.response_id = r.id and a.question_id = q.id);

-- Comments (standard surveys, long text for the custom one). Two demo comments carry an
-- e-mail address and a phone number so the Responses tab can show masking.
insert into answers (tenant_id, response_id, question_id, value_text)
select '00000000-0000-4000-8000-000000000001', r.id, q.id, r.comment
from (
  select r.*,
    case
      when r.slug = 'nps' and r.i = 7
        then 'Please write to anna.virtanen@example.org about the membership fee.'
      when r.slug = 'nps' and r.i = 19
        then 'Call me on +358 40 123 4567 about the volunteer evenings.'
      when r.slug = 'services' and r.i % 2 = 0
        then r.comments[1 + (r.i * 5) % array_length(r.comments, 1)]
      when r.slug <> 'services' and r.i % 3 <> 0
        then r.comments[1 + (r.i * 5) % array_length(r.comments, 1)]
    end as comment
  from seed_resp r
) r
join questions q on q.survey_id = r.survey_id
  and q.position = case when r.slug = 'services' then 4 else 3 end
where r.comment is not null
  and not exists (select 1 from answers a where a.response_id = r.id and a.question_id = q.id);

-- Student services: services used (one to three options) and campus (dropdown).
insert into answers (tenant_id, response_id, question_id, value_choices)
select '00000000-0000-4000-8000-000000000001', r.id, q.id,
  case q.position
    when 1 then (
      select jsonb_agg(q.options ->> k order by n)
      from unnest(case r.i % 3
                    when 0 then array[(r.i * 2) % 5]
                    when 1 then array[(r.i * 2) % 5, (r.i * 2 + 1) % 5]
                    else array[(r.i * 2) % 5, (r.i * 2 + 2) % 5, (r.i * 2 + 4) % 5] end)
           with ordinality as u(k, n))
    else jsonb_build_array(q.options ->> ((r.i * 7) % 3))
  end
from seed_resp r
join questions q on q.survey_id = r.survey_id and q.position in (1, 3)
where r.slug = 'services'
  and not exists (select 1 from answers a where a.response_id = r.id and a.question_id = q.id);

-- Totals, computed from the seeded answers. Uses "do update" on purpose so a re-run keeps
-- them equal to the answers. Like the worker, only a scale first question (thumbs, nps,
-- rating) gets a distribution; other kinds store {}.
insert into survey_aggregates (survey_id, tenant_id, response_count, distribution)
select s.survey_id, '00000000-0000-4000-8000-000000000001',
  (select count(*) from responses r where r.survey_id = s.survey_id),
  coalesce((
    select jsonb_object_agg(d.k, d.c)
    from (
      select a.value_number::int::text as k, count(*) as c
      from answers a
      join questions q on q.id = a.question_id and q.position = 1
        and q.kind in ('thumbs', 'nps', 'rating')
      where q.survey_id = s.survey_id and a.value_number is not null
      group by 1
    ) d), '{}'::jsonb)
from seed_surveys s
on conflict (survey_id) do update
  set response_count = excluded.response_count, distribution = excluded.distribution;

-- Link views per channel: a few times the responses that came in through it.
insert into survey_channel_views (survey_id, tenant_id, channel, view_count)
select s.survey_id, '00000000-0000-4000-8000-000000000001', c.channel,
  (select count(*) from responses r where r.survey_id = s.survey_id
     and r.channel = c.channel) * c.factor + s.idx * 7
from seed_surveys s
cross join (values ('email'::distribution_channel, 3), ('link', 4), ('qr', 6)) as c(channel, factor)
on conflict (survey_id, channel) do nothing;

-- Contact requests: identified respondents who asked to be contacted, in every status.
insert into contact_requests (id, tenant_id, survey_id, response_id, contact_ref, status,
                              created_at)
select md5('contact-' || r.id)::uuid, '00000000-0000-4000-8000-000000000001', r.survey_id,
       r.id, r.contact_ref,
       (array['new','contacted','done'])[1 + (r.i / 3) % 3]::contact_request_status,
       r.submitted_at + interval '1 hour'
from seed_resp r
where r.contact_ref is not null
on conflict (id) do nothing;

commit;

-- ---------------------------------------------------------------------------
-- A second organisation, Example Sports Club, to show that organisations are
-- kept apart: the user menu switches to it (dev auth only). It has its own user,
-- a live thumbs survey and a closed NPS survey with responses, and a draft.
-- ---------------------------------------------------------------------------

begin;

select set_config('app.tenant_id', '00000000-0000-4000-8000-000000000002', true);

insert into tenants (id, name) values
  ('00000000-0000-4000-8000-000000000002', 'Example Sports Club')
on conflict (id) do nothing;

insert into users (id, tenant_id, name, email) values
  ('00000000-0000-4000-8000-000000000102', '00000000-0000-4000-8000-000000000002',
   'Mikko Korhonen', 'mikko.korhonen@example.org')
on conflict (id) do nothing;

insert into surveys (id, tenant_id, title, type, status, created_by, created_at, opens_at,
                     closes_at, published_at, link_token, accent_color, background_color) values
  ('00000000-0000-4000-8000-000000000221', '00000000-0000-4000-8000-000000000002',
   'Training session feedback', 'thumbs', 'live', '00000000-0000-4000-8000-000000000102',
   '2026-09-05 18:00+03', '2026-09-08 18:00+03', null, '2026-09-08 18:00+03',
   'demo-training-feedback-0221', '#1B4F9C', '#F6F7F9'),
  ('00000000-0000-4000-8000-000000000222', '00000000-0000-4000-8000-000000000002',
   'Season pass NPS', 'nps', 'closed', '00000000-0000-4000-8000-000000000102',
   '2026-09-05 18:30+03', '2026-09-10 09:00+03', '2026-11-10 18:00+02', '2026-09-10 09:00+03',
   'demo-season-pass-0222', '#1B4F9C', '#FFFFFF'),
  ('00000000-0000-4000-8000-000000000223', '00000000-0000-4000-8000-000000000002',
   'Club kit order', 'custom', 'draft', '00000000-0000-4000-8000-000000000102',
   '2026-11-02 12:00+02', null, null, null, null, '#1B4F9C', '#FFFFFF')
on conflict (id) do nothing;

insert into survey_links (link_token, survey_id, tenant_id)
select link_token, id, tenant_id from surveys
where id in ('00000000-0000-4000-8000-000000000221', '00000000-0000-4000-8000-000000000222')
on conflict do nothing;

insert into questions (tenant_id, survey_id, position, kind, prompt, options, required) values
  ('00000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-000000000221', 1, 'thumbs',
   'How was today''s training?', '[]', true),
  ('00000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-000000000221', 2, 'reasons',
   'What could be better?',
   '["Too crowded","Too hard","Too easy","Start time","Equipment"]', false),
  ('00000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-000000000221', 3, 'text',
   'Anything else for the coaches?', '[]', false),
  ('00000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-000000000222', 1, 'nps',
   'How likely are you to recommend an Example Sports Club season pass to a friend?', '[]', true),
  ('00000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-000000000222', 2, 'reasons',
   'What shaped your score?',
   '["Coaching","Opening hours","Price","Facilities","Club spirit"]', false),
  ('00000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-000000000222', 3, 'text',
   'Anything else you want to tell us?', '[]', false),
  ('00000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-000000000223', 1,
   'single_choice', 'Which shirt size do you need?', '["XS","S","M","L","XL"]', true),
  ('00000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-000000000223', 2,
   'multiple_choice', 'What else would you order?', '["Shorts","Socks","Training jacket"]', false)
on conflict (survey_id, position) do nothing;

create temp table club_resp on commit drop as
select b.*,
  case b.slug
    -- Thumbs: 0 Not for me, 1 Good, 2 Loved it.
    when 'training' then case when b.i % 6 = 0 then 0 when b.i % 6 in (1, 3) then 1 else 2 end
    else (array[2,5,6,7,8,8,9,9,9,10,10,6,7,9,10])[1 + (b.i * 7) % 15]
  end as score,
  case when b.i % 4 <> 0 then b.comments[1 + (b.i * 3) % array_length(b.comments, 1)] end
    as comment
from (
  select s.survey_id, s.slug, s.comments, g as i,
    md5('resp-club-' || s.slug || '-' || g)::uuid as id,
    md5('link-club-' || s.slug || '-' || g) as link_token_hash,
    ((s.first_day + floor((g - 1) * s.days::numeric / s.n) * interval '1 day'
      + ((g * 5) % 4) * interval '1 hour') at time zone 'Europe/Helsinki') as submitted_at,
    (array['link','email','qr'])[1 + g % 3] as channel
  from (values
    ('00000000-0000-4000-8000-000000000221'::uuid, 'training', 24,
     '2026-09-08 20:00'::timestamp, 70, array[
       'Great session, thanks!',
       'The hall was too full on Tuesday.',
       'More stretching at the end, please.',
       'Coach Leena explains things really well.',
       'Could we start 30 minutes later?']),
    ('00000000-0000-4000-8000-000000000222'::uuid, 'pass', 30,
     '2026-09-10 12:00'::timestamp, 60, array[
       'The weekend opening hours are too short.',
       'Good value for the whole family.',
       'The changing rooms need an update.',
       'Friendly staff and a good club spirit.'])
  ) as s(survey_id, slug, n, first_day, days, comments)
  cross join lateral generate_series(1, s.n) g
) b;

insert into responses (id, tenant_id, survey_id, submitted_at, link_token_hash, channel)
select id, '00000000-0000-4000-8000-000000000002', survey_id, submitted_at, link_token_hash,
       channel::distribution_channel
from club_resp
on conflict (survey_id, link_token_hash) do nothing;

insert into answers (tenant_id, response_id, question_id, value_number)
select '00000000-0000-4000-8000-000000000002', r.id, q.id, r.score
from club_resp r
join questions q on q.survey_id = r.survey_id and q.position = 1
where not exists (select 1 from answers a where a.response_id = r.id and a.question_id = q.id);

-- Reasons: thumbs only after "Not for me", NPS for everyone.
insert into answers (tenant_id, response_id, question_id, value_choices)
select '00000000-0000-4000-8000-000000000002', r.id, q.id,
  jsonb_build_array(q.options ->> ((r.i * 3) % 5))
from club_resp r
join questions q on q.survey_id = r.survey_id and q.position = 2
where (r.slug = 'pass' or r.score = 0)
  and not exists (select 1 from answers a where a.response_id = r.id and a.question_id = q.id);

insert into answers (tenant_id, response_id, question_id, value_text)
select '00000000-0000-4000-8000-000000000002', r.id, q.id, r.comment
from club_resp r
join questions q on q.survey_id = r.survey_id and q.position = 3
where r.comment is not null
  and not exists (select 1 from answers a where a.response_id = r.id and a.question_id = q.id);

insert into survey_aggregates (survey_id, tenant_id, response_count, distribution)
select s.id, '00000000-0000-4000-8000-000000000002',
  (select count(*) from responses r where r.survey_id = s.id),
  coalesce((
    select jsonb_object_agg(d.k, d.c)
    from (
      select a.value_number::int::text as k, count(*) as c
      from answers a
      join questions q on q.id = a.question_id and q.position = 1
      where q.survey_id = s.id and a.value_number is not null
      group by 1
    ) d), '{}'::jsonb)
from surveys s
where s.id in ('00000000-0000-4000-8000-000000000221', '00000000-0000-4000-8000-000000000222')
on conflict (survey_id) do update
  set response_count = excluded.response_count, distribution = excluded.distribution;

insert into survey_channel_views (survey_id, tenant_id, channel, view_count)
select s.id, '00000000-0000-4000-8000-000000000002', c.channel,
  (select count(*) from responses r where r.survey_id = s.id and r.channel = c.channel)
    * c.factor + 5
from surveys s
cross join (values ('email'::distribution_channel, 3), ('link', 4), ('qr', 6)) as c(channel, factor)
where s.id in ('00000000-0000-4000-8000-000000000221', '00000000-0000-4000-8000-000000000222')
on conflict (survey_id, channel) do nothing;

commit;

-- Built-in templates are product content and come from the migrations
-- (20261117090000_templates_and_thank_you.sql), not from this demo seed.

