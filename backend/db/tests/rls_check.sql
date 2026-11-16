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

  -- 3. Another tenant sees none of the demo tenant's rows.
  perform set_config('app.tenant_id', '00000000-0000-4000-8000-0000000000ff', true);
  select count(*) into n from surveys;
  if n <> 0 then raise exception 'RLS: other tenant sees % surveys', n; end if;

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
