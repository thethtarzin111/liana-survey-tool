"""Port: sending survey events to Liana.

The rest of the system only knows this interface. Adapters decide where the
event really goes (mock, LianaAutomation, ...).
"""

from typing import Protocol

from liana_survey_shared.messages import ContactRequested


class ContactEvents(Protocol):
    def send_contact_requested(self, event: ContactRequested) -> None:
        """Deliver the event. Raise TemporaryError to retry later."""
        ...


class TemporaryError(Exception):
    """Liana is down or slow. The connector retries with back-off."""
