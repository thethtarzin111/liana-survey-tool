-- migrate:up
-- "Notify me of new responses by email" (#47). Stored only; sending the emails is #128.
alter table surveys add column notify_on_response boolean not null default false;

-- migrate:down
alter table surveys drop column notify_on_response;
