# Privacy and GDPR

Rules the code follows (R05):

- **Anonymous by default.** In anonymous mode the link token is not linked to
  the recipient, so answers cannot be traced to a person.
- **Identified mode only after opt-in.** Then `responses.contact_ref` holds a
  LianaMailer contact id, not an e-mail address.
- **No recipient e-mail addresses** are stored in the survey database. They are
  only used by LianaMailer to send the link.
- **Tenant isolation** with `tenant_id` and row-level security on every table,
  checked in CI (`db/tests/rls_check.sql`).
- **EU hosting** for every deployment, including demos.
- **Demo data only** in this repo and in demos.

## To decide with Liana
- How long answers are kept, and whether they are deleted or anonymised after that.
- How a respondent's request to delete their answer reaches us.
- Whether Liana's existing data processing agreement covers the survey tool.
