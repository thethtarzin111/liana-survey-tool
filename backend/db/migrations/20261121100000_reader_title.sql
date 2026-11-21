-- migrate:up
-- The title readers see on the survey link page (#105). Template surveys keep their
-- name private ("Name (only you see this)"); custom surveys show their title instead.
alter table surveys
  add column reader_title text check (char_length(reader_title) <= 80);

-- migrate:down
alter table surveys drop column reader_title;
