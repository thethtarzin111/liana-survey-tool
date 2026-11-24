# Privacy and GDPR

Rules the code follows (R05):

- **Anonymous by default.** In anonymous mode the link token is not linked to
  the recipient, so answers cannot be traced to a person.
- **Identified only after opt-in, or when the survey says so.** An answer gets a
  contact (`responses.contact_ref`, a LianaMailer contact id, never an e-mail
  address) when the reader ticks "Contact me", or when the survey's owner set it
  to identified answers (`surveys.anonymous` off, under Survey settings). The
  answer page then tells the reader that their answer is linked to their contact
  details. Only newsletter links carry a contact: answers from the public link and
  the QR code always stay anonymous, and those pages have no "Contact me".
- **Mail scanners do not answer.** Opening an answer link saves nothing; the page
  saves the answer itself. So an email security scanner that opens every link
  never gives an answer, or sends one to LianaAutomation, in someone's name.
- **No recipient e-mail addresses** are stored in the survey database. They are
  only used by LianaMailer to send the link.
- **Tenant isolation** with `tenant_id` and row-level security on every table,
  checked in CI (`backend/db/tests/rls_check.sql`).
- **EU hosting** for every deployment, including demos.
- **Demo data only** in this repo and in demos.

## To decide with Liana
- Whether identified answers need more than the notice on the answer page (for
  example a line in the newsletter itself).
- How long answers are kept, and whether they are deleted or anonymised after that.
- How a respondent's request to delete their answer reaches us.
- Whether Liana's existing data processing agreement covers the survey tool.
