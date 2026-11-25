"""What the connector does with each message on survey.liana-events. Kept free
of RabbitMQ code so it can be tested on its own."""

import logging
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, ValidationError

from liana_survey_shared.messages import AnswerRecorded, ContactRequested, NewResponsesDigest

from .notifications import new_responses_email
from .ports.contact_events import ContactEvents, TemporaryError
from .ports.notification_mail import NotificationMail
from .retry import MAX_ATTEMPTS, backoff_seconds

log = logging.getLogger(__name__)

LianaEvent = Annotated[
    AnswerRecorded | ContactRequested | NewResponsesDigest, Field(discriminator="type")
]
_events = TypeAdapter(LianaEvent)


class BadMessage(Exception):
    """The message has an unknown type or a wrong shape. It goes to the
    dead-letter queue instead of being retried."""


def parse(body: bytes) -> AnswerRecorded | ContactRequested | NewResponsesDigest:
    try:
        return _events.validate_json(body)
    except ValidationError as error:
        raise BadMessage(f"not a Liana event ({error.error_count()} errors)") from error


def handle_event(body: bytes, contacts: ContactEvents, mail: NotificationMail) -> None:
    """Pass one message to the port for its type."""
    _dispatch(parse(body), contacts, mail)


def _dispatch(
    event: AnswerRecorded | ContactRequested | NewResponsesDigest,
    contacts: ContactEvents,
    mail: NotificationMail,
) -> None:
    if isinstance(event, NewResponsesDigest):
        mail.send(new_responses_email(event))
    elif isinstance(event, AnswerRecorded):
        contacts.send_answer_recorded(event)
    else:
        contacts.send_contact_requested(event)


@dataclass(frozen=True)
class Outcome:
    """What to do with the message: acknowledge it, publish it again after
    `delay` seconds, or send it to the dead-letter queue."""

    action: Literal["ack", "retry", "dead"]
    delay: float = 0.0


def deliver(body: bytes, attempt: int, contacts: ContactEvents, mail: NotificationMail) -> Outcome:
    """Deliver one message. `attempt` starts at 1.

    A TemporaryError (Liana down or slow) is retried with back-off until
    MAX_ATTEMPTS; after the last one the port records the event as failed, so the
    sync log offers Retry. Any other error does not go away by retrying (the sync
    log has it, or it is a bug), so the message goes to the dead-letter queue."""
    try:
        event = parse(body)
    except BadMessage:
        log.exception("bad message, sending to dead letter")
        return Outcome("dead")
    try:
        _dispatch(event, contacts, mail)
    except TemporaryError as error:
        if attempt < MAX_ATTEMPTS:
            delay = backoff_seconds(attempt)
            log.warning(
                "temporary error, retry %s in %ss message=%s: %s",
                attempt,
                delay,
                event.message_id,
                error,
            )
            return Outcome("retry", delay)
        log.error("giving up after %s attempts message=%s: %s", attempt, event.message_id, error)
        if not isinstance(event, NewResponsesDigest):
            try:
                contacts.give_up(event, str(error))
            except Exception:
                log.exception("could not mark message=%s as failed", event.message_id)
        return Outcome("dead")
    except Exception:
        log.exception("could not deliver message=%s, sending to dead letter", event.message_id)
        return Outcome("dead")
    return Outcome("ack")
