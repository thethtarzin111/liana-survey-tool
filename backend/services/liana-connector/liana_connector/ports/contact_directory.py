"""Port: who a LianaMailer contact id is.

LianaAutomation matches contacts by email, but a newsletter link only carries the
reader's LianaMailer contact id (r=). The connector asks this port for the address
before it sends an event. Adapters: the LianaMailer REST API, a demo fake for local
development, and "not set up".
"""

from typing import Protocol


class ContactDirectory(Protocol):
    def email_for(self, contact_id: str) -> str:
        """The contact's email address. Raises ContactNotFound, DirectoryNotSetUp or
        DirectoryUnavailable."""
        ...


class ContactNotFound(Exception):
    """LianaMailer has no contact with this id (or it has no email address)."""


class DirectoryNotSetUp(Exception):
    """The LianaMailer API settings are missing or refused. The message says what to
    fix; events wait as failed, with Retry."""


class DirectoryUnavailable(Exception):
    """LianaMailer is down, slow or rate limited: try again later."""
