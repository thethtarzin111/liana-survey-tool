"""LianaAutomation integration rules: plain Python, no framework code."""

import re
from datetime import datetime
from typing import Any

#: The built-in fake LianaAutomation for local development (AUTH_MODE=dev only).
DEMO_HOST = "demo"
DEFAULT_HOST = "rest.automation.lianacloud.com"
# Only Liana's own hosts, so a saved host can never make the backend call
# another server (and send it the client secret).
_LIANA_HOST = re.compile(r"^(?:[a-z0-9-]+\.)+lianacloud\.com$")

#: What the "Choose what to send" switches start as.
DEFAULT_SETTINGS = {"answers": True, "contact_requests": True, "themes": False}

#: Test events go only to made-up contacts: no real person gets test data.
TEST_DOMAIN = "@example.com"
TEST_EMAIL = "survey-test-1@example.com"


class InvalidInput(ValueError):
    """Bad input from the admin. The message is safe to show."""


def clean_host(host: str, allow_demo: bool) -> str:
    """The host in lower case, without scheme or slashes. Raises InvalidInput unless it
    is a lianacloud.com host, or the demo host when allowed."""
    value = host.strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
    if value == DEMO_HOST and allow_demo:
        return value
    if not _LIANA_HOST.match(value):
        raise InvalidInput("Use a LianaAutomation host ending in lianacloud.com.")
    return value


def secret_hint(secret: str) -> str:
    """The last 4 characters, shown as "••••a91f"; never the whole secret."""
    return secret[-4:] if len(secret) >= 8 else ""


def merged_settings(saved: dict[str, Any] | None, changes: dict[str, Any] | None = None) -> dict:
    """The switches with defaults filled in; unknown keys and non-booleans are dropped."""
    result = dict(DEFAULT_SETTINGS)
    for source in (saved or {}, changes or {}):
        for key, value in source.items():
            if key in DEFAULT_SETTINGS and isinstance(value, bool):
                result[key] = value
    return result


def nps_group(score: int) -> str:
    """detractor (0-6), passive (7-8) or promoter (9-10): easy to filter on in segments."""
    return "detractor" if score <= 6 else "passive" if score <= 8 else "promoter"


def test_contact(email: str | None) -> str:
    """The test contact's email. Raises InvalidInput unless it is an @example.com address."""
    value = (email or TEST_EMAIL).strip().lower()
    if not value.endswith(TEST_DOMAIN) or value.count("@") != 1 or len(value) > 120:
        raise InvalidInput("Test events go only to made-up @example.com contacts.")
    return value


def test_event(email: str, now: datetime, score: int = 3) -> dict[str, Any]:
    """One `data` item for POST /import: a survey_answered event for a test contact.

    `test_sent_at` makes each test unique, so no_duplicates never drops a new test."""
    return {
        "identity": {"email": email},
        "events": [
            {
                "verb": "survey_answered",
                "items": {
                    "survey_id": "test",
                    "survey_name": "Survey tool (test)",
                    "score": str(score),
                    "nps_group": nps_group(score),
                    "campaign": "test",
                    "contact_me": "false",
                    "test_sent_at": now.isoformat(timespec="seconds"),
                },
            }
        ],
    }


def import_body(channel_id: str, data: list[dict[str, Any]]) -> dict[str, Any]:
    """The POST /import body. no_duplicates makes a retry safe: Liana skips an event it
    already has."""
    return {"channel": channel_id, "no_duplicates": True, "data": data}


#: The verb of a "Contact me" request on the contact's timeline.
CONTACT_REQUEST_VERB = "survey_contact_request"
#: The identity a real contact is matched on. The survey tool never stores email
#: addresses (docs/gdpr.md): contact_ref is the LianaMailer contact id from the
#: newsletter link. Check this identity name with Liana on the test account.
CONTACT_IDENTITY = "lianamailer_id"


def contact_request_event(
    contact_ref: str, survey_id: str, contact_request_id: str, requested_at: datetime
) -> dict[str, Any]:
    """One `data` item for POST /import: a reader asked to be contacted.

    contact_request_id makes each request unique, so no_duplicates drops only a
    redelivered copy of the same request."""
    return {
        "identity": {CONTACT_IDENTITY: contact_ref},
        "events": [
            {
                "verb": CONTACT_REQUEST_VERB,
                "items": {
                    "survey_id": str(survey_id),
                    "contact_request_id": str(contact_request_id),
                    "requested_at": requested_at.isoformat(timespec="seconds"),
                },
            }
        ],
    }


#: The verb of an answer on the contact's timeline (the test event uses it too).
ANSWER_VERB = "survey_answered"
#: LianaMailer contact ids are numbers; anything else can't be a contact in Liana.
_CONTACT_ID = re.compile(r"[0-9]{1,20}")
#: Sync log reasons for answers that are deliberately not sent.
NOT_SENT_ANONYMOUS = "Not sent: anonymous answer."
NOT_SENT_UNKNOWN = "Not sent: contact unknown (r={ref})."


def answer_event(
    survey_id: str,
    survey_title: str,
    main_kind: str | None,
    score: int | None,
    campaign: str | None,
    contact_ref: str | None,
) -> tuple[dict[str, Any], str | None]:
    """One `data` item for POST /import: a survey_answered event for the contact, and
    why it must not be sent (None when it may be sent).

    The items are the same each time for the same answer, so a redelivered message
    or a second tap with the same answer is recognised and not sent twice. Never the
    answers' texts: only the score, its NPS group, the survey and the campaign."""
    items: dict[str, str] = {"survey_id": str(survey_id), "survey_name": survey_title}
    if score is not None:
        items["score"] = str(score)
        if main_kind == "nps":
            items["nps_group"] = nps_group(score)
    if campaign:
        items["campaign"] = campaign
    event: dict[str, Any] = {"events": [{"verb": ANSWER_VERB, "items": items}]}
    if contact_ref is None:
        return event, NOT_SENT_ANONYMOUS
    if not _CONTACT_ID.fullmatch(contact_ref):
        shown = masked_email(contact_ref)
        return {"identity": {CONTACT_IDENTITY: contact_ref}, **event}, NOT_SENT_UNKNOWN.format(
            ref=shown
        )
    return {"identity": {CONTACT_IDENTITY: contact_ref}, **event}, None


def sends_answers(connection: dict[str, Any] | None) -> bool:
    """The organisation connected LianaAutomation and left "Survey answers" on."""
    return connection is not None and merged_settings(connection["settings"])["answers"]


def sends_contact_requests(connection: dict[str, Any] | None) -> bool:
    """The organisation connected LianaAutomation and left "Contact me" requests on."""
    return connection is not None and merged_settings(connection["settings"])["contact_requests"]


def not_ready(connection: dict[str, Any]) -> str | None:
    """Why events can't be sent through this connection now, or None. The admin fixes
    it on the Integrations page, then presses Retry in the sync log."""
    if connection["status"] != "connected":
        return "LianaAutomation is not connected. Test the connection, then press Retry."
    if not connection["channel_id"]:
        return "No channel chosen. Choose one, then press Retry."
    return None


def contact_of(payload: dict[str, Any]) -> str | None:
    """The contact in a stored event (email, or the contact id), for the sync log."""
    identity = payload.get("identity") or {}
    return identity.get("email") or identity.get(CONTACT_IDENTITY)


def masked_email(contact: str | None) -> str | None:
    """Shortened to "su…@example.com" (or "C-…" for a contact id): enough to recognise
    a contact, not the whole address or id."""
    if not contact:
        return None
    if "@" not in contact:
        return f"{contact[:2]}…"
    name, domain = contact.split("@", 1)
    return f"{name[:2]}…@{domain}"
