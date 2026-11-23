"""Connector entry point: consume survey.liana-events and pass each message to
the adapter for its type ("Contact me" requests, "new responses" emails).

A message that hit a temporary error is published again after a back-off delay,
with its attempt number in the ATTEMPT_HEADER. The original stays unacknowledged
until the copy is published, so a crash in between redelivers it instead of
losing it. After MAX_ATTEMPTS it goes to the dead-letter queue.
"""

import asyncio
import logging

import aio_pika

from liana_survey_shared import queues
from liana_survey_shared.config import get_settings

from .delivery_status import record_contact_request_status
from .factory import build_contact_events, build_notification_mail
from .handlers import RecordStatus, deliver
from .ports.contact_events import ContactEvents
from .ports.notification_mail import NotificationMail

log = logging.getLogger("liana_connector")

ATTEMPT_HEADER = "x-attempt"
#: Messages handled at the same time, including those waiting for a retry.
PREFETCH = 20


def attempt_of(message: aio_pika.abc.AbstractIncomingMessage) -> int:
    try:
        return max(1, int((message.headers or {}).get(ATTEMPT_HEADER, 1)))
    except (TypeError, ValueError):
        return 1


async def retry_later(
    channel: aio_pika.abc.AbstractChannel,
    message: aio_pika.abc.AbstractIncomingMessage,
    attempt: int,
    delay: float,
) -> None:
    """Publish a copy with the next attempt number after `delay`, then ack the original."""
    await asyncio.sleep(delay)
    try:
        await channel.default_exchange.publish(
            aio_pika.Message(
                message.body,
                content_type=message.content_type,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=message.message_id,
                headers={**(message.headers or {}), ATTEMPT_HEADER: attempt + 1},
            ),
            routing_key=queues.LIANA_EVENTS,
        )
    except Exception:
        log.exception("could not publish the retry, putting the message back")
        await message.nack(requeue=True)
        return
    await message.ack()


async def process(
    channel: aio_pika.abc.AbstractChannel,
    message: aio_pika.abc.AbstractIncomingMessage,
    contacts: ContactEvents,
    mail: NotificationMail,
    record: RecordStatus,
    pending: set[asyncio.Task],
) -> None:
    attempt = attempt_of(message)
    # The adapters and the status update block, so they run off the event loop.
    outcome = await asyncio.to_thread(deliver, message.body, attempt, contacts, mail, record)
    if outcome.action == "ack":
        await message.ack()
    elif outcome.action == "dead":
        await message.reject(requeue=False)
    else:
        task = asyncio.create_task(retry_later(channel, message, attempt, outcome.delay))
        pending.add(task)
        task.add_done_callback(pending.discard)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    contacts = build_contact_events(settings)
    mail = build_notification_mail(settings)
    conn = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with conn:
        channel = await conn.channel(publisher_confirms=True)
        await channel.set_qos(prefetch_count=PREFETCH)
        await channel.declare_queue(queues.DEAD_LETTER, durable=True)
        queue = await channel.declare_queue(
            queues.LIANA_EVENTS,
            durable=True,
            arguments=queues.LIANA_EVENTS_ARGUMENTS,
        )
        log.info(
            "connector listening on %s (adapter=%s)", queues.LIANA_EVENTS, settings.liana_adapter
        )
        pending: set[asyncio.Task] = set()
        async with queue.iterator() as messages:
            async for message in messages:
                await process(
                    channel, message, contacts, mail, record_contact_request_status, pending
                )


if __name__ == "__main__":
    asyncio.run(main())
