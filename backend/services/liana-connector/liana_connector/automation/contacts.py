"""The contact's email address for an event, before it goes to LianaAutomation.

LianaAutomation matches contacts by email. An event from a newsletter answer is
stored with the reader's LianaMailer contact id (domain.CONTACT_IDENTITY); this
looks the address up (LianaMailer API, through the ContactDirectory port) and puts
it in the identity. Addresses are kept for a day in lianamailer_contacts, so a
second tap does not call LianaMailer again.

The API is called outside any database transaction, as calls to Liana are.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import timedelta
from typing import Any
from uuid import UUID

import psycopg

from ..ports.contact_directory import (
    ContactDirectory,
    ContactNotFound,
    DirectoryNotSetUp,
    DirectoryUnavailable,
)
from . import domain, repo

#: How long a looked-up address is used before LianaMailer is asked again.
CACHE_FOR = timedelta(days=1)

Db = Callable[[], AbstractContextManager[psycopg.Connection]]


class NotSent(Exception):
    """LianaMailer has no such contact: the event is not sent (status skipped)."""


class LookupFailed(Exception):
    """The address could not be looked up now (LianaMailer not set up, refused or
    down). The event waits as failed, with Retry."""


def with_email(
    payload: dict[str, Any],
    directory: ContactDirectory,
    db: Db,
    response_id: UUID | None = None,
) -> dict[str, Any]:
    """The payload with {"email": ...} as its identity. A payload that has an address
    already (the test event, a request from the public page) is returned as it is.

    With `response_id`, the address is also saved on that response if the reader
    asked to be contacted (repo.save_contact_email), for Results -> Responses.
    Raises NotSent or LookupFailed; their message is the sync log's reason."""
    identity = payload.get("identity") or {}
    contact_id = identity.get(domain.CONTACT_IDENTITY)
    if not contact_id:
        return payload
    with db() as conn:
        email = repo.cached_email(conn, contact_id, CACHE_FOR)
    if email is None:
        try:
            email = directory.email_for(contact_id)
        except ContactNotFound:
            raise NotSent(domain.not_found(contact_id)) from None
        except (DirectoryNotSetUp, DirectoryUnavailable) as error:
            raise LookupFailed(str(error)) from None
        with db() as conn:
            repo.cache_email(conn, contact_id, email, CACHE_FOR)
    if response_id is not None:
        with db() as conn:
            repo.save_contact_email(conn, response_id, email)
    return {**payload, "identity": {"email": email}}
