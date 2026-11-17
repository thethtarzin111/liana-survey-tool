"""The real answer path through RabbitMQ (#113): respondent service -> survey.answers
-> worker process -> database, and broken messages -> survey.dead-letter.

Needs a migrated Postgres (reached as the app role) and RabbitMQ. CI's db job has
both and sets REQUIRE_DB and REQUIRE_RABBITMQ; elsewhere the tests skip unless both
answer. The surveys they create are deleted afterwards.
"""

import asyncio
import os
import secrets
import subprocess
import sys
import time
from urllib.parse import urlsplit
from uuid import UUID

import aio_pika
import pytest
from fastapi.testclient import TestClient

from liana_survey_shared import links, queues
from liana_survey_shared.config import get_settings
from liana_survey_shared.db import ping, tenant_connection

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")
WAIT_SECONDS = 20


def rabbitmq_answers() -> bool:
    async def check():
        conn = await aio_pika.connect(get_settings().rabbitmq_url, timeout=2)
        await conn.close()

    try:
        asyncio.run(check())
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (os.environ.get("REQUIRE_DB") or ping())
    or not (os.environ.get("REQUIRE_RABBITMQ") or rabbitmq_answers()),
    reason="needs Postgres and RabbitMQ (set DATABASE_URL and RABBITMQ_URL)",
)


async def _with_channel(work):
    conn = await aio_pika.connect(get_settings().rabbitmq_url, timeout=5)
    async with conn:
        channel = await conn.channel()
        await channel.declare_queue(queues.DEAD_LETTER, durable=True)
        answers = await channel.declare_queue(
            queues.ANSWERS, durable=True, arguments=queues.ANSWERS_ARGUMENTS
        )
        return await work(channel, answers)


def purge_queues() -> None:
    async def work(channel, answers):
        await answers.purge()
        await (await channel.get_queue(queues.DEAD_LETTER)).purge()

    asyncio.run(_with_channel(work))


def publish_raw(body: bytes) -> None:
    async def work(channel, answers):
        await channel.default_exchange.publish(aio_pika.Message(body), routing_key=queues.ANSWERS)

    asyncio.run(_with_channel(work))


def dead_letters() -> list[bytes]:
    async def work(channel, answers):
        dead = await channel.get_queue(queues.DEAD_LETTER)
        bodies = []
        while (message := await dead.get(fail=False)) is not None:
            bodies.append(message.body)
            await message.ack()
        return bodies

    return asyncio.run(_with_channel(work))


@pytest.fixture
def worker():
    """The worker as its own process, as in production."""
    purge_queues()
    process = subprocess.Popen(
        [sys.executable, "-m", "survey_worker.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    yield process
    process.terminate()
    try:
        output, _ = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        output, _ = process.communicate()
    print(output)  # shown by pytest when a test fails


@pytest.fixture
def live_survey():
    """A live NPS survey with a public link, deleted afterwards."""
    token = secrets.token_urlsafe(16)
    with tenant_connection(DEMO_TENANT) as conn:
        survey_id = conn.execute(
            """insert into surveys (tenant_id, title, type, status, link_token)
               values (%s, 'Queue test', 'nps', 'live', %s) returning id""",
            (DEMO_TENANT, token),
        ).fetchone()[0]
        conn.execute(
            """insert into questions (tenant_id, survey_id, position, kind, prompt)
               values (%s, %s, 1, 'nps', 'Main?')""",
            (DEMO_TENANT, survey_id),
        )
        conn.execute(
            "insert into survey_links (link_token, survey_id, tenant_id) values (%s, %s, %s)",
            (token, survey_id, DEMO_TENANT),
        )
    yield survey_id, token
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("delete from surveys where id = %s", (survey_id,))


def tap(client, token, reader, answer) -> int:
    settings = get_settings()
    url = links.answer_link(settings.public_base_url, settings.link_signing_secret, token, reader)
    parts = urlsplit(url)
    return client.get(f"{parts.path}?{parts.query}&a={answer}").status_code


def totals(survey_id):
    with tenant_connection(DEMO_TENANT) as conn:
        row = conn.execute(
            "select response_count, distribution from survey_aggregates where survey_id = %s",
            (survey_id,),
        ).fetchone()
    return (row[0], row[1]) if row else (0, {})


def wait_for(check, worker):
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        if (result := check()) is not None:
            return result
        assert worker.poll() is None, "the worker stopped"
        time.sleep(0.2)
    pytest.fail("timed out waiting for the worker")


def test_a_tap_travels_through_rabbitmq_and_is_saved_once(worker, live_survey):
    from respondent_service.main import app

    survey_id, token = live_survey
    with TestClient(app) as client:
        assert tap(client, token, "reader-1", 9) == 200
        assert wait_for(lambda: totals(survey_id) if totals(survey_id)[0] else None, worker) == (
            1,
            {"9": 1},
        )

        # The same reader again, then someone else: the first answer counts once.
        assert tap(client, token, "reader-1", 3) == 200
        assert tap(client, token, "reader-2", 10) == 200
        final = wait_for(lambda: totals(survey_id) if totals(survey_id)[0] >= 2 else None, worker)
    assert final == (2, {"9": 1, "10": 1})


def test_a_broken_message_goes_to_the_dead_letter_queue(worker):
    publish_raw(b"not an answer")
    assert wait_for(lambda: dead_letters() or None, worker) == [b"not an answer"]
