"""LianaMailer adapter for the contact directory: the email address of a contact id.

LianaMailer REST API v1 (https://rest.lianamailer.com/docs/):

    POST https://{host}/api/v1/getRecipient
    body (v1 parameters are positional): [<id>, {"include_consents": false, ...}]
    answer: {"succeed": true, "result": {"recipient": {"id": .., "email": ..}}}

Signed with HMAC-SHA256 (the docs' "Using HMAC signature"), with the API user id,
secret and realm from Liana:

    Content-Type:  application/json
    Content-MD5:   md5 hex of the body
    Date:          the time, e.g. 2026-11-25T12:00:00+00:00
    Authorization: {realm} {user id}:{signature}

    signature = hex HMAC-SHA256(secret, "\\n".join(
        [method, content md5, content type, date, body, path]))

The body that is signed must be byte for byte the body that is sent. What the API
answers for an id that does not exist is not in the docs; "succeed": false, a 404
or a recipient without an email address all count as "not found".
"""

import hashlib
import hmac
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from ...ports.contact_directory import ContactNotFound, DirectoryNotSetUp, DirectoryUnavailable

log = logging.getLogger(__name__)

CONTENT_TYPE = "application/json"
GET_RECIPIENT = "/api/v1/getRecipient"
OPTIONS = {
    "include_consents": False,
    "include_list_memberships": False,
    "include_properties": False,
}
#: The settings to name when something is missing or refused.
SETTINGS = "LIANAMAILER_API_HOST, LIANAMAILER_API_USER, LIANAMAILER_API_SECRET"
#: The built-in fake for local development (AUTH_MODE=dev only), like the demo
#: LianaAutomation host.
DEMO_HOST = "demo"


def signature(secret: str, method: str, md5: str, date: str, body: str, path: str) -> str:
    """The HMAC-SHA256 signature of one request, as lowercase hex."""
    message = "\n".join([method, md5, CONTENT_TYPE, date, body, path])
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def signed_headers(
    realm: str, user: str, secret: str, method: str, body: str, path: str, date: str
) -> dict[str, str]:
    """The headers of a signed request."""
    md5 = hashlib.md5(body.encode()).hexdigest()  # the API asks for MD5, not for security
    return {
        "Content-Type": CONTENT_TYPE,
        "Content-MD5": md5,
        "Date": date,
        "Authorization": f"{realm} {user}:{signature(secret, method, md5, date, body, path)}",
    }


class LianaMailerDirectory:
    """Looks contacts up with POST /api/v1/getRecipient."""

    def __init__(
        self,
        host: str,
        user: str,
        secret: str,
        realm: str = "EUR",
        *,
        http: httpx.Client | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.base = "https://" + host.strip().removeprefix("https://").rstrip("/")
        self.user = user.strip()
        self.secret = secret
        self.realm = realm.strip() or "EUR"
        self.http = http or httpx.Client(timeout=10)
        self.now = now

    def email_for(self, contact_id: str) -> str:
        if not contact_id.isdigit():
            raise ContactNotFound(contact_id)  # LianaMailer ids are numbers
        body = json.dumps([int(contact_id), OPTIONS], separators=(",", ":"))
        date = self.now().isoformat(timespec="seconds")
        headers = signed_headers(
            self.realm, self.user, self.secret, "POST", body, GET_RECIPIENT, date
        )
        try:
            res = self.http.post(self.base + GET_RECIPIENT, content=body.encode(), headers=headers)
        except httpx.HTTPError as error:
            raise DirectoryUnavailable("Could not reach LianaMailer. Try again later.") from error
        # The status only: the body holds the contact's email address.
        log.info("LianaMailer getRecipient %s: HTTP %s", contact_id, res.status_code)
        if res.status_code in (401, 403):
            raise DirectoryNotSetUp(
                f"LianaMailer refused the API credentials ({res.status_code}). Check {SETTINGS}"
                " and LIANAMAILER_API_REALM on the server."
            )
        if res.status_code == 429 or res.status_code >= 500:
            raise DirectoryUnavailable(f"LianaMailer answered {res.status_code}. Try again later.")
        if res.status_code == 404:
            raise ContactNotFound(contact_id)
        try:
            answer: Any = res.json()
        except ValueError as error:
            raise DirectoryUnavailable("LianaMailer gave an unexpected answer.") from error
        return _email(answer, contact_id)


def _email(answer: Any, contact_id: str) -> str:
    """The address in a getRecipient answer. Raises ContactNotFound."""
    if not isinstance(answer, dict) or answer.get("succeed") is False:
        raise ContactNotFound(contact_id)
    result = answer.get("result")
    recipient = result.get("recipient") if isinstance(result, dict) else None
    email = recipient.get("email") if isinstance(recipient, dict) else None
    if not isinstance(email, str) or "@" not in email:
        raise ContactNotFound(contact_id)
    return email.strip().lower()


class DemoDirectory:
    """A fake LianaMailer for local development: every contact id of five or more
    digits is contact.<id>@example.com, so no real person ever gets demo events.
    Shorter ids (e.g. 999) are not found, and ids ending in 666 get an address with
    "fail" in it, which the demo LianaAutomation answers with an error (to try Retry).
    """

    def email_for(self, contact_id: str) -> str:
        if not contact_id.isdigit() or len(contact_id) < 5:
            raise ContactNotFound(contact_id)
        if contact_id.endswith("666"):
            return f"fail.{contact_id}@example.com"
        return f"contact.{contact_id}@example.com"


class NotSetUp:
    """No LianaMailer API settings on this server."""

    def __init__(self, reason: str | None = None) -> None:
        self.reason = reason or (
            f"The LianaMailer API is not set up on the server ({SETTINGS}), so the contact's"
            " email address can't be looked up. Set it up, then press Retry."
        )

    def email_for(self, contact_id: str) -> str:
        raise DirectoryNotSetUp(self.reason)
