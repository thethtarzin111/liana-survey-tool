"""Puts answers on the survey.answers queue for the worker (#23) to save."""

import asyncio

import aio_pika

from liana_survey_shared import queues
from liana_survey_shared.messages import AnswerSubmitted


class AnswerQueue:
    """One RabbitMQ connection per process, opened on the first answer and
    reconnected by aio-pika when it drops."""

    def __init__(self, url: str):
        self._url = url
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._lock = asyncio.Lock()

    async def _ready(self) -> aio_pika.abc.AbstractChannel:
        async with self._lock:
            if self._channel is None or self._channel.is_closed:
                self._connection = await aio_pika.connect_robust(self._url, timeout=5)
                self._channel = await self._connection.channel(publisher_confirms=True)
                await self._channel.declare_queue(queues.DEAD_LETTER, durable=True)
                await self._channel.declare_queue(
                    queues.ANSWERS, durable=True, arguments=queues.ANSWERS_ARGUMENTS
                )
            return self._channel

    async def publish(self, message: AnswerSubmitted) -> None:
        """Returns once RabbitMQ has the message (publisher confirms), so a thank-you
        page is only shown for answers that will be saved."""
        channel = await self._ready()
        await channel.default_exchange.publish(
            aio_pika.Message(
                message.model_dump_json().encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=str(message.message_id),
            ),
            routing_key=queues.ANSWERS,
        )

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
