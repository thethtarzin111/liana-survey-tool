-- migrate:up
-- Whether a "Contact me" request reached LianaAutomation (#58). The worker creates
-- the request as 'pending'; the connector sets 'sent', or 'failed' once it gives up.
alter table contact_requests
  add column liana_status text not null default 'pending'
    check (liana_status in ('pending', 'sent', 'failed')),
  add column liana_attempts integer not null default 0 check (liana_attempts >= 0),
  add column liana_updated_at timestamptz;

-- One request per response: a reader who taps again keeps their first request.
create unique index contact_requests_response_id_key on contact_requests (response_id);

-- migrate:down
drop index if exists contact_requests_response_id_key;
alter table contact_requests
  drop column liana_updated_at,
  drop column liana_attempts,
  drop column liana_status;
