"""Mock notification mail: the default until a real mail adapter exists. Logs
the subject and text and keeps each email in memory, so tests and demos can
check what would have been sent."""

import logging

from ...ports.notification_mail import Email

log = logging.getLogger(__name__)


class MockNotificationMail:
    def __init__(self) -> None:
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)
        log.info(
            "[mock mail] to=%s subject=%r\n%s", email.to_name, email.subject, email.text.rstrip()
        )
