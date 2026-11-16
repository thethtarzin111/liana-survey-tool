"""Worker entry point: consume survey.answers."""

import asyncio
import logging

import aio_pika
from pydantic import ValidationError

from liana_survey_shared import queues
from liana_survey_shared.config import get_settings

from .handlers import handle_answer

log = logging.getLogger("survey_worker")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    conn = await aio_pika.connect_robust(get_settings().rabbitmq_url)
    async with conn:
        channel = await conn.channel()
        await channel.set_qos(prefetch_count=20)
        await channel.declare_queue(queues.DEAD_LETTER, durable=True)
        queue = await channel.declare_queue(
            queues.ANSWERS,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": queues.DEAD_LETTER,
            },
        )
        log.info("worker listening on %s", queues.ANSWERS)
        async with queue.iterator() as messages:
            async for message in messages:
                try:
                    handle_answer(message.body)
                    await message.ack()
                except ValidationError:
                    log.exception("bad message, sending to dead letter")
                    await message.reject(requeue=False)


if __name__ == "__main__":
    asyncio.run(main())
