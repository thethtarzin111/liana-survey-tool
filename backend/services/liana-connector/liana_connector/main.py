"""Connector entry point: consume survey.liana-events and pass them to the adapter.

TODO (backlog card "Retry failed Liana calls"): on TemporaryError, re-publish
with a delay from retry.backoff_seconds() instead of rejecting.
"""

import asyncio
import logging

import aio_pika
from pydantic import ValidationError

from liana_survey_shared import queues
from liana_survey_shared.config import get_settings
from liana_survey_shared.messages import ContactRequested

from .factory import build_contact_events

log = logging.getLogger("liana_connector")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    events = build_contact_events(settings)
    conn = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with conn:
        channel = await conn.channel()
        await channel.declare_queue(queues.DEAD_LETTER, durable=True)
        queue = await channel.declare_queue(
            queues.LIANA_EVENTS,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": queues.DEAD_LETTER,
            },
        )
        log.info(
            "connector listening on %s (adapter=%s)", queues.LIANA_EVENTS, settings.liana_adapter
        )
        async with queue.iterator() as messages:
            async for message in messages:
                try:
                    events.send_contact_requested(
                        ContactRequested.model_validate_json(message.body)
                    )
                    await message.ack()
                except ValidationError:
                    log.exception("bad message, sending to dead letter")
                    await message.reject(requeue=False)


if __name__ == "__main__":
    asyncio.run(main())
