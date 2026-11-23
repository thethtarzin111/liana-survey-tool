"""What the connector does with each message on survey.liana-events. Kept free
of RabbitMQ code so it can be tested on its own."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, ValidationError

from liana_survey_shared.messages import ContactRequested, NewResponsesDigest

from .notifications import new_responses_email
from .ports.contact_events import ContactEvents, TemporaryError
from .ports.notification_mail import NotificationMail
from .retry import MAX_ATTEMPTS, backoff_seconds

log = logging.getLogger(__name__)

LianaEvent = Annotated[ContactRequested | NewResponsesDigest, Field(discriminator="type")]
_events = TypeAdapter(LianaEvent)

DeliveryStatus = Literal["pending", "sent", "failed"]
#: Stores how a contact request's delivery went: (event, status, attempts so far).
RecordStatus = Callable[[ContactRequested, DeliveryStatus, int], None]


class BadMessage(Exception):
    """The message has an unknown type or a wrong shape. It goes to the
    dead-letter queue instead of being retried."""


def parse(body: bytes) -> ContactRequested | NewResponsesDigest:
    try:
        return _events.validate_json(body)
    except ValidationError as error:
        raise BadMessage(f"not a Liana event ({error.error_count()} errors)") from error


def handle_event(body: bytes, contacts: ContactEvents, mail: NotificationMail) -> None:
    """Pass one message to the port for its type."""
    _dispatch(parse(body), contacts, mail)


def _dispatch(
    event: ContactRequested | NewResponsesDigest, contacts: ContactEvents, mail: NotificationMail
) -> None:
    if isinstance(event, NewResponsesDigest):
        mail.send(new_responses_email(event))
    else:
        contacts.send_contact_requested(event)


@dataclass(frozen=True)
class Outcome:
    """What to do with the message: acknowledge it, publish it again after
    `delay` seconds, or send it to the dead-letter queue."""

    action: Literal["ack", "retry", "dead"]
    delay: float = 0.0


def deliver(
    body: bytes,
    attempt: int,
    contacts: ContactEvents,
    mail: NotificationMail,
    record: RecordStatus,
) -> Outcome:
    """Deliver one message. `attempt` starts at 1.

    A TemporaryError is retried with back-off until MAX_ATTEMPTS. Any other
    error does not go away by retrying, so the message goes to the dead-letter
    queue at once. A contact request's result is stored through `record`."""
    try:
        event = parse(body)
    except BadMessage:
        log.exception("bad message, sending to dead letter")
        return Outcome("dead")
    try:
        _dispatch(event, contacts, mail)
    except TemporaryError:
        if attempt >= MAX_ATTEMPTS:
            log.exception("giving up after %s attempts message=%s", attempt, event.message_id)
            _record(record, event, "failed", attempt)
            return Outcome("dead")
        delay = backoff_seconds(attempt)
        log.warning("temporary error, retry %s in %ss message=%s", attempt, delay, event.message_id)
        _record(record, event, "pending", attempt)
        return Outcome("retry", delay)
    except Exception:
        log.exception("could not deliver, sending to dead letter message=%s", event.message_id)
        _record(record, event, "failed", attempt)
        return Outcome("dead")
    _record(record, event, "sent", attempt)
    return Outcome("ack")


def _record(
    record: RecordStatus,
    event: ContactRequested | NewResponsesDigest,
    status: DeliveryStatus,
    attempts: int,
) -> None:
    """Store a contact request's result. The status is only shown to people, so
    a failure to store it is logged and does not change the delivery."""
    if not isinstance(event, ContactRequested):
        return
    try:
        record(event, status, attempts)
    except Exception:
        log.exception(
            "could not store status %s for contact request %s", status, event.contact_request_id
        )
