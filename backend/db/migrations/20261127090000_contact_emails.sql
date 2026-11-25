-- migrate:up

-- "Contact me" requests live on the response (Results -> Responses, filter "Asked to
-- be contacted"), whether or not they reach LianaAutomation.
alter table responses
  add column contact_requested    boolean not null default false,
  add column contact_requested_at timestamptz,
  -- Only for readers who asked to be contacted: the address LianaMailer gave for
  -- their contact id, or the one they typed on the public page. Never for others.
  add column contact_email        text check (char_length(contact_email) <= 254);

create index responses_contact_requested on responses (survey_id)
  where contact_requested;

-- A request from the public page has an email address, not a LianaMailer contact id.
alter table contact_requests alter column contact_ref drop not null;

-- LianaMailer contact id -> email, looked up by the connector before it sends an
-- event to LianaAutomation (which matches contacts by email). Kept for a day, so a
-- second tap does not call the LianaMailer API again; older rows are deleted.
create table lianamailer_contacts (
  tenant_id   uuid not null references tenants(id) on delete cascade,
  contact_id  text not null,
  email       text not null check (char_length(email) <= 254),
  fetched_at  timestamptz not null default now(),
  primary key (tenant_id, contact_id)
);

alter table lianamailer_contacts enable row level security;
alter table lianamailer_contacts force row level security;
create policy tenant_isolation on lianamailer_contacts
  using (tenant_id = app_tenant_id()) with check (tenant_id = app_tenant_id());

-- The sync log keeps LianaAutomation's answer to each send (status and body, email
-- addresses hidden), for its Details view, and the contact shortened ("te…@example.com")
-- for its Contact column. The payload keeps the LianaMailer contact id: the address is
-- added only when the event is sent, and never stored here.
alter table integration_events
  add column liana_response text,
  add column contact_hint   text;

-- migrate:down

alter table integration_events drop column contact_hint, drop column liana_response;
drop table lianamailer_contacts;
delete from contact_requests where contact_ref is null;
alter table contact_requests alter column contact_ref set not null;
drop index responses_contact_requested;
alter table responses
  drop column contact_email,
  drop column contact_requested_at,
  drop column contact_requested;
