-- migrate:up
-- "You said, we did" (#63): resolving a contact request sends the reader the
-- team's message through the connector. reply_status works like liana_status:
-- 'pending' until the connector has passed the message on, then 'sent', or
-- 'failed' once it gives up. Null until the request is resolved.
alter table contact_requests
  add column reply_text text check (char_length(reply_text) between 1 and 1000),
  add column reply_status text check (reply_status in ('pending', 'sent', 'failed')),
  add column reply_attempts integer not null default 0 check (reply_attempts >= 0),
  add column resolved_at timestamptz;

-- migrate:down
alter table contact_requests
  drop column resolved_at,
  drop column reply_attempts,
  drop column reply_status,
  drop column reply_text;
