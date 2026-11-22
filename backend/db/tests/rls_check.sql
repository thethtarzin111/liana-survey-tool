-- Run as the app role (survey_app) after migrations + seed.
-- Fails (raises) if tenant isolation does not work. Used by CI.

do $$
declare n integer;
begin
  -- 1. No tenant set: nothing is visible.
  perform set_config('app.tenant_id', '', true);
  select count(*) into n from surveys;
  if n <> 0 then raise exception 'RLS: % surveys visible without a tenant', n; end if;

  -- 2. Demo tenant: its own survey is visible, plus the built-in templates.
  perform set_config('app.tenant_id', '00000000-0000-4000-8000-000000000001', true);
  select count(*) into n from surveys;
  if n < 1 then raise exception 'RLS: demo tenant cannot see its own surveys'; end if;
  select count(*) into n from templates where tenant_id is null;
  if n < 3 then raise exception 'RLS: built-in templates not visible (got %)', n; end if;

  -- A logo for the demo survey, to check that logos are isolated as well.
  insert into survey_logos (survey_id, tenant_id, content_type, data)
  values ('00000000-0000-4000-8000-000000000201', '00000000-0000-4000-8000-000000000001',
          'image/png', '\x89504e47'::bytea)
  on conflict (survey_id) do nothing;

  -- 3. Another tenant sees none of the demo tenant's rows.
  perform set_config('app.tenant_id', '00000000-0000-4000-8000-0000000000ff', true);
  select count(*) into n from surveys;
  if n <> 0 then raise exception 'RLS: other tenant sees % surveys', n; end if;
  select count(*) into n from survey_logos;
  if n <> 0 then raise exception 'RLS: other tenant sees % survey logos', n; end if;

  perform set_config('app.tenant_id', '00000000-0000-4000-8000-000000000001', true);
  delete from survey_logos where survey_id = '00000000-0000-4000-8000-000000000201';
  perform set_config('app.tenant_id', '00000000-0000-4000-8000-0000000000ff', true);

  -- 3c. A link can only be added by the survey's own organisation.
  begin
    insert into survey_links (link_token, survey_id, tenant_id)
    values ('sneakysneakysneakysneaky', '00000000-0000-4000-8000-000000000201',
            '00000000-0000-4000-8000-000000000001');
    raise exception 'RLS: cross-tenant survey link was allowed';
  exception when insufficient_privilege then
    null; -- expected
  end;

  -- 3d. "New responses" email state is isolated; the sweep's function sees ids only.
  perform set_config('app.tenant_id', '00000000-0000-4000-8000-000000000001', true);
  insert into surveys (id, tenant_id, title, type, created_by, notify_on_response)
  values ('00000000-0000-4000-8000-0000000002f1', '00000000-0000-4000-8000-000000000001',
          'RLS digest check', 'nps', '00000000-0000-4000-8000-000000000101', true);
  insert into survey_aggregates (survey_id, tenant_id, response_count)
  values ('00000000-0000-4000-8000-0000000002f1', '00000000-0000-4000-8000-000000000001', 2);
  insert into response_notifications (survey_id, tenant_id, notified_count)
  values ('00000000-0000-4000-8000-0000000002f1', '00000000-0000-4000-8000-000000000001', 1);

  perform set_config('app.tenant_id', '00000000-0000-4000-8000-0000000000ff', true);
  select count(*) into n from response_notifications;
  if n <> 0 then raise exception 'RLS: other tenant sees % response notifications', n; end if;
  begin
    update response_notifications set notified_count = 0;
    get diagnostics n = row_count;
    if n <> 0 then raise exception 'RLS: other tenant updated % response notifications', n; end if;
    insert into response_notifications (survey_id, tenant_id, notified_count)
    values ('00000000-0000-4000-8000-000000000201', '00000000-0000-4000-8000-000000000001', 0);
    raise exception 'RLS: cross-tenant response notification was allowed';
  exception when insufficient_privilege then
    null; -- expected
  end;
  select count(*) into n from due_response_digests(3600)
  where survey_id = '00000000-0000-4000-8000-0000000002f1'
    and tenant_id = '00000000-0000-4000-8000-000000000001';
  if n <> 1 then raise exception 'due_response_digests() did not find a due survey'; end if;

  perform set_config('app.tenant_id', '00000000-0000-4000-8000-000000000001', true);
  delete from surveys where id = '00000000-0000-4000-8000-0000000002f1';
  perform set_config('app.tenant_id', '00000000-0000-4000-8000-0000000000ff', true);

  -- 3e. Link view counts for survey performance are isolated.
  perform set_config('app.tenant_id', '00000000-0000-4000-8000-000000000001', true);
  insert into survey_channel_views (survey_id, tenant_id, channel, view_count)
  values ('00000000-0000-4000-8000-000000000201', '00000000-0000-4000-8000-000000000001', 'qr', 1)
  on conflict (survey_id, channel) do nothing;
  perform set_config('app.tenant_id', '00000000-0000-4000-8000-0000000000ff', true);
  select count(*) into n from survey_channel_views;
  if n <> 0 then raise exception 'RLS: other tenant sees % survey channel views', n; end if;
  begin
    insert into survey_channel_views (survey_id, tenant_id, channel, view_count)
    values ('00000000-0000-4000-8000-000000000201', '00000000-0000-4000-8000-000000000001', 'email', 1);
    raise exception 'RLS: cross-tenant survey channel view was allowed';
  exception when insufficient_privilege then
    null; -- expected
  end;
  perform set_config('app.tenant_id', '00000000-0000-4000-8000-000000000001', true);
  delete from survey_channel_views
  where survey_id = '00000000-0000-4000-8000-000000000201' and channel = 'qr';

  -- 3f. An organisation's own template is hidden from other organisations,
  --     and nobody can change it but its owner.
  perform set_config('app.tenant_id', '00000000-0000-4000-8000-000000000001', true);
  insert into templates (id, tenant_id, name, type)
  values ('00000000-0000-4000-8000-0000000003ff', '00000000-0000-4000-8000-000000000001',
          'Demo org template', 'custom');
  perform set_config('app.tenant_id', '00000000-0000-4000-8000-0000000000ff', true);
  select count(*) into n from templates where tenant_id is not null;
  if n <> 0 then raise exception 'RLS: other tenant sees % own templates', n; end if;
  update templates set name = 'sneaky' where id = '00000000-0000-4000-8000-0000000003ff';
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'RLS: other tenant renamed a template'; end if;
  delete from templates where id = '00000000-0000-4000-8000-0000000003ff';
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'RLS: other tenant deleted a template'; end if;
  perform set_config('app.tenant_id', '00000000-0000-4000-8000-000000000001', true);
  delete from templates where id = '00000000-0000-4000-8000-0000000003ff';
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'RLS: demo tenant cannot delete its own template'; end if;

  -- 3g. Built-in templates are read-only.
  update templates set name = 'sneaky' where tenant_id is null;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'RLS: % built-in templates renamed', n; end if;
  delete from templates where tenant_id is null;
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'RLS: % built-in templates deleted', n; end if;
  begin
    insert into templates (tenant_id, name, type) values (null, 'sneaky', 'custom');
    raise exception 'RLS: a built-in template was added';
  exception when insufficient_privilege then
    null; -- expected
  end;
  perform set_config('app.tenant_id', '00000000-0000-4000-8000-0000000000ff', true);

  -- 4. Writing a row for a different tenant is refused.
  begin
    insert into surveys (tenant_id, title, type)
    values ('00000000-0000-4000-8000-000000000001', 'sneaky', 'nps');
    raise exception 'RLS: cross-tenant insert was allowed';
  exception when insufficient_privilege then
    null; -- expected: new row violates row-level security policy
  end;

  raise notice 'RLS check passed';
end $$;
