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


def contact_of(payload: dict[str, Any]) -> str | None:
    """The contact's email in a stored event, for the sync log."""
    identity = payload.get("identity") or {}
    return identity.get("email")


def masked_email(email: str | None) -> str | None:
    """Shortened to "su…@example.com": enough to recognise a test contact, not a whole
    address."""
    if not email or "@" not in email:
        return None
    name, domain = email.split("@", 1)
    return f"{name[:2]}…@{domain}"
