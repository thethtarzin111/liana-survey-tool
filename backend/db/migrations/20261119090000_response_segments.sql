-- migrate:up
alter table responses add column segment text not null default 'all'
  check (segment ~ '^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$');
create index responses_survey_segment_idx on responses (survey_id, segment);

-- migrate:down
drop index if exists responses_survey_segment_idx;
alter table responses drop column segment;
