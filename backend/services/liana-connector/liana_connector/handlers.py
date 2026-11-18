"""What the connector does with each message on survey.liana-events. Kept free
of RabbitMQ code so it can be tested on its own."""

from typing import Annotated

from pydantic import Field, TypeAdapter, ValidationError

from liana_survey_shared.messages import ContactRequested, NewResponsesDigest

from .notifications import new_responses_email
from .ports.contact_events import ContactEvents
from .ports.notification_mail import NotificationMail

LianaEvent = Annotated[ContactRequested | NewResponsesDigest, Field(discriminator="type")]
_events = TypeAdapter(LianaEvent)


class BadMessage(Exception):
    """The message has an unknown type or a wrong shape. It goes to the
    dead-letter queue instead of being retried."""


def handle_event(body: bytes, contacts: ContactEvents, mail: NotificationMail) -> None:
    """Pass one message to the port for its type."""
    try:
        event = _events.validate_json(body)
    except ValidationError as error:
        raise BadMessage(f"not a Liana event ({error.error_count()} errors)") from error
    if isinstance(event, NewResponsesDigest):
        mail.send(new_responses_email(event))
    else:
        contacts.send_contact_requested(event)
