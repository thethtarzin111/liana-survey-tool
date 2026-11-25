"""Port: sending survey events to Liana.

The rest of the system only knows this interface. Adapters decide where the
event really goes (mock, LianaAutomation, ...).
"""

from typing import Protocol

from liana_survey_shared.messages import AnswerRecorded, ContactRequested


class ContactEvents(Protocol):
    def send_contact_requested(self, event: ContactRequested) -> None:
        """Deliver the event. Raise TemporaryError to retry later."""
        ...

    def send_answer_recorded(self, event: AnswerRecorded) -> None:
        """Deliver a saved answer (survey_answered), or record why it is not sent.
        Raise TemporaryError to retry later."""
        ...

    def give_up(self, event: AnswerRecorded | ContactRequested, reason: str) -> None:
        """The connector stops retrying the event after its last attempt. Record it
        as failed (the sync log offers Retry). `reason` is the last error."""
        ...


class TemporaryError(Exception):
    """Liana is down or slow. The connector retries with back-off."""
