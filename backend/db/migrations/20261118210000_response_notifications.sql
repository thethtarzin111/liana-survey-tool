-- migrate:up

-- "New responses" emails to a survey's owner. One row per survey with
-- notify_on_response on: when the last email went out and how many responses
-- (survey_aggregates.response_count) it covered. The worker writes it; the email
-- itself only travels on the queue to the Liana connector.
create table response_notifications (
  survey_id       uuid primary key references surveys(id) on delete cascade,
  tenant_id       uuid not null references tenants(id) on delete cascade,
  -- Null until the first email for this survey went out.
  last_sent_at    timestamptz,
  notified_count  integer not null check (notified_count >= 0)
);

alter table response_notifications enable row level security;
alter table response_notifications force row level security;
create policy tenant_isolation on response_notifications
  using (tenant_id = app_tenant_id()) with check (tenant_id = app_tenant_id());

-- The worker's periodic sweep needs the surveys of every organisation whose
-- digest email is due. This is the only read across organisations besides the
-- survey_links lookup. It returns ids only; the worker then reads and claims each
-- survey through its own tenant connection. Security definer: it runs as the
-- migration owner, which must bypass row-level security (the superuser that runs
-- migrations does).
create function due_response_digests(interval_seconds integer)
  returns table (survey_id uuid, tenant_id uuid)
  language sql stable security definer
  set search_path = public, pg_temp
  as $$
    select n.survey_id, n.tenant_id
    from response_notifications n
    join surveys s on s.id = n.survey_id
    join survey_aggregates a on a.survey_id = n.survey_id
    where s.notify_on_response
      and s.created_by is not null
      and a.response_count > n.notified_count
      and (n.last_sent_at is null
           or n.last_sent_at <= now() - make_interval(secs => interval_seconds))
  $$;

-- migrate:down

drop function due_response_digests(integer);
drop table response_notifications;
