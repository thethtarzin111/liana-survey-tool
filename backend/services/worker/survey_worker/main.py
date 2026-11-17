"""Worker entry point: consume survey.answers."""

import asyncio
import logging

import aio_pika
import psycopg

from liana_survey_shared import queues
from liana_survey_shared.config import get_settings

from .handlers import BadMessage, handle_answer

log = logging.getLogger("survey_worker")

#: Wait before retrying after the database could not be reached.
RETRY_DELAY_SECONDS = 5


async def process(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """Save one message. Bad messages go to the dead-letter queue; when the
    database is unreachable the message is put back and retried later."""
    try:
        # The database calls are blocking, so they run off the event loop.
        await asyncio.to_thread(handle_answer, message.body)
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
        await message.ack()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    conn = await aio_pika.connect_robust(get_settings().rabbitmq_url)
    async with conn:
        channel = await conn.channel()
        await channel.set_qos(prefetch_count=20)
        await channel.declare_queue(queues.DEAD_LETTER, durable=True)
        queue = await channel.declare_queue(
            queues.ANSWERS, durable=True, arguments=queues.ANSWERS_ARGUMENTS
        )
        log.info("worker listening on %s", queues.ANSWERS)
        async with queue.iterator() as messages:
            async for message in messages:
                await process(message)


if __name__ == "__main__":
    asyncio.run(main())
