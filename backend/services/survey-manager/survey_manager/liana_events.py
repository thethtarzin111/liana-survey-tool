"""Puts messages for other Liana products on the survey.liana-events queue,
where the Liana connector picks them up."""

import asyncio
from typing import Protocol

import aio_pika
from fastapi import Request

from liana_survey_shared import queues
from liana_survey_shared.config import get_settings
from liana_survey_shared.messages import Message


class LianaEvents(Protocol):
    async def publish(self, message: Message) -> None: ...


class LianaEventQueue:
    """One RabbitMQ connection per process, opened on the first message and
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
                    queues.LIANA_EVENTS, durable=True, arguments=queues.LIANA_EVENTS_ARGUMENTS
                )
            return self._channel

    async def publish(self, message: Message) -> None:
        """Returns once RabbitMQ has the message (publisher confirms)."""
        channel = await self._ready()
        await channel.default_exchange.publish(
            aio_pika.Message(
                message.model_dump_json().encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=str(message.message_id),
            ),
            routing_key=queues.LIANA_EVENTS,
        )

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()


def get_liana_events(request: Request) -> LianaEvents:
    """The process's publisher, made on first use. The local gateway sets its own
    (straight to the connector code) when RabbitMQ is not running."""
    state = request.app.state
    if getattr(state, "liana_events", None) is None:
        state.liana_events = LianaEventQueue(get_settings().rabbitmq_url)
    return state.liana_events
