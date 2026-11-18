"""Port: emails to app users, such as the "new responses" email to a survey's owner.

Adapters decide how the email is really sent. Only the mock exists so far.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Email:
    to_address: str
    to_name: str
    subject: str
    text: str


class NotificationMail(Protocol):
    def send(self, email: Email) -> None:
        """Send the email. Raise ports.contact_events.TemporaryError to retry later."""
        ...
