-- migrate:up

-- Publishing (#5): a live survey gets a random, hard-to-guess public token that
-- its answer links use (/r/<token>). It is set on the first publish and kept, so
-- links already sent keep working if the survey is unpublished and published again.
alter table surveys
  add column link_token text unique check (link_token ~ '^[A-Za-z0-9_-]{20,64}$'),
  add column published_at timestamptz;

-- migrate:down

alter table surveys
  drop column published_at,
  drop column link_token;
