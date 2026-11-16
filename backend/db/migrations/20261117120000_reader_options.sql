-- migrate:up

-- Reader options from "Edit and preview". All on by default, as in the prototype.
alter table surveys
  -- "Tell us more" after any answer.
  add column comment_field boolean not null default true,
  -- Readers see the results after answering (once there are about 10 answers).
  add column show_results boolean not null default true,
  -- "Contact me about this by email" opt-in. Answers stay anonymous unless the
  -- reader ticks it; then a contact request is created with a contact reference,
  -- never an e-mail address (see liana_survey_shared.contact).
  add column contact_opt_in boolean not null default true;

-- migrate:down

alter table surveys
  drop column contact_opt_in,
  drop column show_results,
  drop column comment_field;
