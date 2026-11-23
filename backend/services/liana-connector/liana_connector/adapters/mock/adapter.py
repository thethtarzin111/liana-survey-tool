"""Mock adapter: the default until staging access works. Logs the event and
keeps it in memory so tests and demos can check what would have been sent."""

import logging

from liana_survey_shared.messages import ContactRequested, ContactResolved

log = logging.getLogger(__name__)


class MockContactEvents:
    def __init__(self) -> None:
        self.sent: list[ContactRequested] = []
        self.resolved: list[ContactResolved] = []

    def send_contact_requested(self, event: ContactRequested) -> None:
        self.sent.append(event)
        log.info("[mock LianaAutomation] contact.requested survey=%s", event.survey_id)

    def send_contact_resolved(self, event: ContactResolved) -> None:
        self.resolved.append(event)
        log.info(
            "[mock LianaAutomation] contact.resolved survey=%s contact=%s\n%s",
            event.survey_id,
            event.contact_ref,
            event.message,
        )
