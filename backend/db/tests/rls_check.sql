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
