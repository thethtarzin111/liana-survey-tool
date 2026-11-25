# Privacy and GDPR

Rules the code follows (R05):

- **The public link and the QR code are anonymous.** Their answers keep only a
  random visit key, so they cannot be traced to a person.
- **Newsletter answers are identified.** A newsletter link carries the reader's
  LianaMailer contact id (`r=`). It is stored with the answer
  (`responses.contact_ref`), the answer is sent to LianaAutomation as a
  `survey_answered` event, and the answer page tells the reader: "Your answer is
  linked to your contact details with the sender."
- **E-mail addresses only where they are needed.**
  - LianaAutomation matches contacts by e-mail, so the connector looks the
    contact id up in LianaMailer (API) right before it sends an event. The
    address is kept for one day in `lianamailer_contacts`, so a second tap does
    not call the API again; older rows are deleted.
  - An address is stored with an answer (`responses.contact_email`) only when the
    reader asked to be contacted: looked up in LianaMailer for a newsletter
    reader, or typed by the reader on the public page (required there once they
    tick "Contact me"). Results → Responses shows it only on those rows, under
    "Asked to be contacted"; every other row stays anonymised.
  - The sync log (`integration_events`) never keeps a full address: its rows hold
    the contact id (or a reference to the response), and the address is added only
    for the call to LianaAutomation. For display a row keeps a shortened form
    (`contact_hint`, "te…@example.com"): still personal data, but not an address
    anyone can write to. It goes with the row (the sync log is per organisation).
  - Everything kept or logged from LianaAutomation (error messages in `last_error`,
    the answer in `liana_response`) has its email addresses replaced by `[email]`
    (`automation.domain.hide_emails`, applied in `LianaError` and to every answer).
    It is a best-effort safety net: an unusual address could slip through.
  - The connector logs only the status of a LianaMailer lookup, never its body.
- **Mail scanners do not answer.** Opening an answer link saves nothing; the page
  saves the answer itself, so an email security scanner that opens every link
  never gives an answer, or sends one to LianaAutomation, in someone's name.
- **Server settings stay on the server.** The LianaMailer API user and secret are
  environment variables (`LIANAMAILER_API_*`), never in the repo or the front end.
- **Tenant isolation** with `tenant_id` and row-level security on every table,
  checked in CI (`backend/db/tests/rls_check.sql`).
- **EU hosting** for every deployment, including demos.
- **Demo data only** in this repo and in demos.

## To decide with Liana
- Whether identifying newsletter answers needs more than the notice on the answer
  page (for example a line in the newsletter itself, or a consent in LianaMailer).
- How long the e-mail addresses of contact requests are kept.
- How long answers are kept, and whether they are deleted or anonymised after that.
- How a respondent's request to delete their answer reaches us.
- Whether Liana's existing data processing agreement covers the survey tool.
