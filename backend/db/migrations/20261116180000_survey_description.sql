-- migrate:up

alter table surveys add column description text;

-- migrate:down

alter table surveys drop column description;
