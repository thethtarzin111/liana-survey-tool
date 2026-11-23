"""Worker entry point: consume survey.answers, and pass "Contact me" requests and
"new responses" emails for survey owners on through survey.liana-events."""

import asyncio
import logging

import aio_pika
import psycopg

from liana_survey_shared import queues
from liana_survey_shared.config import get_settings
from liana_survey_shared.messages import Message

from .digests import Publish, sweep_forever
from .handlers import BadMessage, record_answer

log = logging.getLogger("survey_worker")

#: Wait before retrying after the database could not be reached.
RETRY_DELAY_SECONDS = 5


async def process(message: aio_pika.abc.AbstractIncomingMessage, publish: Publish) -> None:
    """Save one message. Bad messages go to the dead-letter queue; when the
    database is unreachable the message is put back and retried later.

    A contact request or "new responses" email that the answer created is
    published before the ack. If publishing fails, the answer stays saved: the
    email is skipped, and the contact request stays 'pending' on the Contact
    requests page."""
    try:
        # The database calls are blocking, so they run off the event loop.
        recorded = await asyncio.to_thread(record_answer, message.body)
    except BadMessage:
        log.exception("bad message, sending to dead letter")
        await message.reject(requeue=False)
    except psycopg.OperationalError:
        log.exception("database unavailable, retrying in %ss", RETRY_DELAY_SECONDS)
        await asyncio.sleep(RETRY_DELAY_SECONDS)
        await message.nack(requeue=True)
    except Exception:
        log.exception("could not save message, sending to dead letter")
        await message.reject(requeue=False)
    else:
        if recorded.contact_request is not None:
            try:
                await publish(recorded.contact_request)
            except Exception:
                log.exception("could not publish the contact request, it stays pending")
        if recorded.digest is not None:
            try:
                await publish(recorded.digest)
            except Exception:
                log.exception("could not publish the new responses email, skipping it")
        await message.ack()


def publisher(channel: aio_pika.abc.AbstractChannel) -> Publish:
    async def publish(event: Message) -> None:
        await channel.default_exchange.publish(
            aio_pika.Message(
                event.model_dump_json().encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=str(event.message_id),
            ),
            routing_key=queues.LIANA_EVENTS,
        )
        log.info("%s queued message=%s", getattr(event, "type", "event"), event.message_id)

    return publish


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    conn = await aio_pika.connect_robust(get_settings().rabbitmq_url)
    async with conn:
        channel = await conn.channel(publisher_confirms=True)
        await channel.set_qos(prefetch_count=20)
        await channel.declare_queue(queues.DEAD_LETTER, durable=True)
        await channel.declare_queue(
            queues.LIANA_EVENTS, durable=True, arguments=queues.LIANA_EVENTS_ARGUMENTS
        )
        queue = await channel.declare_queue(
            queues.ANSWERS, durable=True, arguments=queues.ANSWERS_ARGUMENTS
        )
        publish = publisher(channel)
        sweeper = asyncio.create_task(sweep_forever(publish))
        log.info("worker listening on %s", queues.ANSWERS)
        try:
            async with queue.iterator() as messages:
                async for message in messages:
                    await process(message, publish)
        finally:
            sweeper.cancel()


if __name__ == "__main__":
    asyncio.run(main())
