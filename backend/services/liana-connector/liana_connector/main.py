"""Connector entry point: consume survey.liana-events and pass each message to
the adapter for its type ("Contact me" requests, "new responses" emails).

TODO (backlog card "Retry failed Liana calls"): on TemporaryError, re-publish
with a delay from retry.backoff_seconds() instead of rejecting.
"""

import asyncio
import logging

import aio_pika

from liana_survey_shared import queues
from liana_survey_shared.config import get_settings

from .factory import build_contact_events, build_notification_mail
from .handlers import BadMessage, handle_event

log = logging.getLogger("liana_connector")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    events = build_contact_events(settings)
    mail = build_notification_mail(settings)
    conn = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with conn:
        channel = await conn.channel()
        await channel.declare_queue(queues.DEAD_LETTER, durable=True)
        queue = await channel.declare_queue(
            queues.LIANA_EVENTS,
            durable=True,
            arguments=queues.LIANA_EVENTS_ARGUMENTS,
        )
        log.info(
            "connector listening on %s (adapter=%s)", queues.LIANA_EVENTS, settings.liana_adapter
        )
        async with queue.iterator() as messages:
            async for message in messages:
                try:
                    handle_event(message.body, events, mail)
                    await message.ack()
                except BadMessage:
                    log.exception("bad message, sending to dead letter")
                    await message.reject(requeue=False)


if __name__ == "__main__":
    asyncio.run(main())
