-- migrate:up
-- Newsletter snippet links (#40) are not signed per reader. Only surveys whose
-- snippet was made accept them; every other survey keeps needing signed links.
alter table surveys add column newsletter_links boolean not null default false;

-- migrate:down
alter table surveys drop column newsletter_links;
