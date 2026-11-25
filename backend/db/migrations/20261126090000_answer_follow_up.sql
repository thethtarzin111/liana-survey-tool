-- migrate:up

-- The "Tell us more" box (surveys.comment_field) on the answer pages. Only used
-- when the survey has no text question of its own; Results shows it as the comment.
alter table responses
  add column comment text check (char_length(comment) <= 5000);

-- One "Contact me" request per response: a reader who sends the follow-up page
-- again keeps their first request. (#182 adds the same index.)
create unique index if not exists contact_requests_response_id_key
  on contact_requests (response_id);

-- Answers the connector deliberately did not send (anonymous, or an unknown
-- contact) are in the sync log too, so it is always clear why something did not
-- reach LianaAutomation.
alter table integration_events drop constraint integration_events_status_check;
alter table integration_events add constraint integration_events_status_check
  check (status in ('pending', 'sent', 'retrying', 'failed', 'skipped'));

-- One survey_answered row per response: a changed answer updates its row.
create unique index integration_events_response_verb
  on integration_events (response_id, verb) where response_id is not null;

-- migrate:down

drop index integration_events_response_verb;
delete from integration_events where status = 'skipped';
alter table integration_events drop constraint integration_events_status_check;
alter table integration_events add constraint integration_events_status_check
  check (status in ('pending', 'sent', 'retrying', 'failed'));
drop index if exists contact_requests_response_id_key;
alter table responses drop column comment;
