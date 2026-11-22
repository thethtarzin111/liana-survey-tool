-- migrate:up
-- Organisations save, rename and delete their own templates.
-- Everyone still reads the built-in templates (tenant_id null), but only the
-- schema owner may change them: the old policy let the app delete them.
drop policy tenant_isolation on templates;
create policy templates_read on templates for select
  using (tenant_id is null or tenant_id = app_tenant_id());
create policy templates_insert on templates for insert
  with check (tenant_id = app_tenant_id());
create policy templates_update on templates for update
  using (tenant_id = app_tenant_id())
  with check (tenant_id = app_tenant_id());
create policy templates_delete on templates for delete
  using (tenant_id = app_tenant_id());

-- migrate:down
drop policy templates_read on templates;
drop policy templates_insert on templates;
drop policy templates_update on templates;
drop policy templates_delete on templates;
create policy tenant_isolation on templates
  using (tenant_id is null or tenant_id = app_tenant_id())
  with check (tenant_id = app_tenant_id());
