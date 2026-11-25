"""Mock adapter: the default until staging access works. Logs the event and
keeps it in memory so tests and demos can check what would have been sent."""

import logging

from liana_survey_shared.messages import AnswerRecorded, ContactRequested

log = logging.getLogger(__name__)


class MockContactEvents:
    def __init__(self) -> None:
        self.sent: list[ContactRequested] = []
        self.answers: list[AnswerRecorded] = []
        self.given_up: list[tuple[AnswerRecorded | ContactRequested, str]] = []

    def send_contact_requested(self, event: ContactRequested) -> None:
        self.sent.append(event)
        log.info("[mock LianaAutomation] contact.requested survey=%s", event.survey_id)

    def send_answer_recorded(self, event: AnswerRecorded) -> None:
        self.answers.append(event)
        log.info(
            "[mock LianaAutomation] answer.recorded survey=%s identified=%s",
            event.survey_id,
            event.contact_ref is not None,
        )

    def give_up(self, event: AnswerRecorded | ContactRequested, reason: str) -> None:
        self.given_up.append((event, reason))
        log.info("[mock LianaAutomation] gave up on %s: %s", event.type, reason)
