-- migrate:up
alter table surveys add column reader_title text;
alter table responses add column channel text not null default 'email'
  check (channel in ('email', 'link', 'qr'));
-- migrate:down
alter table responses drop column channel;
alter table surveys drop column reader_title;
