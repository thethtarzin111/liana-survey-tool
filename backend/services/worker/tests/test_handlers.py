"""The worker saves answers and updates totals (#23).

Tests marked `db` need a migrated Postgres reached as the app role (see
survey-manager's tests); they delete the surveys they create.
"""

import asyncio
import os
from uuid import UUID, uuid4

import psycopg
import pytest

from liana_survey_shared.db import ping, tenant_connection
from liana_survey_shared.messages import AnswerSubmitted, AnswerValue
from survey_worker import main as worker
from survey_worker.handlers import BadMessage, handle_answer, parse

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")
OTHER_TENANT = UUID("00000000-0000-4000-8000-0000000000ff")

needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)


def message(survey_id, answers, *, reader="reader-1", tenant=DEMO_TENANT) -> bytes:
    return (
        AnswerSubmitted(
            tenant_id=tenant,
            survey_id=survey_id,
            link_token_hash=f"key-{reader}",
            answers=answers,
        )
        .model_dump_json()
        .encode()
    )


# --- Without a database ---------------------------------------------------------


def test_garbage_is_a_bad_message():
    with pytest.raises(BadMessage):
        parse(b'{"nope": 1}')
    with pytest.raises(BadMessage):
        handle_answer(b"not json")


class FakeMessage:
    def __init__(self):
        self.body = b"{}"
        self.outcome = None

    async def ack(self):
        self.outcome = "ack"

    async def reject(self, requeue):
        self.outcome = ("reject", requeue)

    async def nack(self, requeue):
        self.outcome = ("nack", requeue)


@pytest.mark.parametrize(
    ("raised", "outcome"),
    [
        (None, "ack"),
        (BadMessage("x"), ("reject", False)),  # to the dead-letter queue
        (RuntimeError("x"), ("reject", False)),
    ],
)
def test_messages_are_acked_or_dead_lettered(monkeypatch, raised, outcome):
    def fake_handle(body):
        if raised:
            raise raised
        return True

    monkeypatch.setattr(worker, "handle_answer", fake_handle)
    msg = FakeMessage()
    asyncio.run(worker.process(msg))
    assert msg.outcome == outcome


def test_database_outages_are_retried_not_dropped(monkeypatch):
    def fake_handle(body):
        raise psycopg.OperationalError("database is down")

    monkeypatch.setattr(worker, "handle_answer", fake_handle)
    monkeypatch.setattr(worker, "RETRY_DELAY_SECONDS", 0)
    msg = FakeMessage()
    asyncio.run(worker.process(msg))
    assert msg.outcome == ("nack", True)


# --- With a database --------------------------------------------------------------


@pytest.fixture
def make_survey():
    """Creates surveys for the demo tenant and deletes them afterwards."""
    made: list[UUID] = []

    def create(kind: str = "nps", survey_type: str = "nps") -> tuple[UUID, UUID, UUID]:
        with tenant_connection(DEMO_TENANT) as conn:
            survey_id = conn.execute(
                """insert into surveys (tenant_id, title, type)
                   values (%s, 'Worker test', %s) returning id""",
                (DEMO_TENANT, survey_type),
            ).fetchone()[0]
            main = conn.execute(
                """insert into questions (tenant_id, survey_id, position, kind, prompt)
                   values (%s, %s, 1, %s, 'Main?') returning id""",
                (DEMO_TENANT, survey_id, kind),
            ).fetchone()[0]
            reasons = conn.execute(
                """insert into questions
                     (tenant_id, survey_id, position, kind, prompt, options, required)
                   values (%s, %s, 2, 'reasons', '', '["Price","Quality"]', false)
                   returning id""",
                (DEMO_TENANT, survey_id),
            ).fetchone()[0]
        made.append(survey_id)
        return survey_id, main, reasons

    yield create
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("delete from surveys where id = any(%s)", (made,))


def totals(survey_id):
    with tenant_connection(DEMO_TENANT) as conn:
        row = conn.execute(
            "select response_count, distribution from survey_aggregates where survey_id = %s",
            (survey_id,),
        ).fetchone()
    return (row[0], row[1]) if row else (0, {})


def stored(survey_id):
    with tenant_connection(DEMO_TENANT) as conn:
        return conn.execute(
            """select r.tenant_id, a.value_number, a.value_choices
               from responses r join answers a on a.response_id = r.id
               where r.survey_id = %s order by a.value_number nulls last""",
            (survey_id,),
        ).fetchall()


def nps(question, score):
    return [AnswerValue(question_id=question, number=score)]


@pytest.mark.db
@needs_db
def test_an_answer_is_saved_for_its_tenant_and_counted(make_survey):
    survey_id, main, reasons = make_survey()
    body = message(
        survey_id,
        [
            AnswerValue(question_id=main, number=9),
            AnswerValue(question_id=reasons, choices=["Price"]),
        ],
    )
    assert handle_answer(body) is True
    assert stored(survey_id) == [(DEMO_TENANT, 9, None), (DEMO_TENANT, None, ["Price"])]
    assert totals(survey_id) == (1, {"9": 1})


@pytest.mark.db
@needs_db
def test_the_same_message_twice_is_counted_once(make_survey):
    survey_id, main, _ = make_survey()
    body = message(survey_id, nps(main, 10))
    assert handle_answer(body) is True
    assert handle_answer(body) is False
    assert totals(survey_id) == (1, {"10": 1})
    assert len(stored(survey_id)) == 1


@pytest.mark.db
@needs_db
def test_the_same_reader_answering_again_is_counted_once(make_survey):
    survey_id, main, _ = make_survey()
    handle_answer(message(survey_id, nps(main, 3), reader="anna"))
    # A new message (new message_id) for the same link: still one answer.
    assert handle_answer(message(survey_id, nps(main, 9), reader="anna")) is False
    assert totals(survey_id) == (1, {"3": 1})


@pytest.mark.db
@needs_db
def test_totals_add_up_per_value(make_survey):
    survey_id, main, _ = make_survey()
    for reader, score in [("a", 9), ("b", 9), ("c", 3), ("d", 10)]:
        handle_answer(message(survey_id, nps(main, score), reader=reader))
    assert totals(survey_id) == (4, {"9": 2, "3": 1, "10": 1})


@pytest.mark.db
@needs_db
@pytest.mark.parametrize(
    ("kind", "survey_type", "value"), [("thumbs", "thumbs", 2), ("rating", "csat", 4)]
)
def test_thumbs_and_csat_answers_are_counted_too(make_survey, kind, survey_type, value):
    survey_id, main, _ = make_survey(kind, survey_type)
    handle_answer(message(survey_id, nps(main, value)))
    assert totals(survey_id) == (1, {str(value): 1})


@pytest.mark.db
@needs_db
def test_custom_surveys_count_responses_without_a_scale(make_survey):
    survey_id, main, _ = make_survey("single_choice", "custom")
    handle_answer(message(survey_id, [AnswerValue(question_id=main, choices=["Yes"])]))
    assert totals(survey_id) == (1, {})


@pytest.mark.db
@needs_db
def test_unknown_surveys_and_questions_are_bad_messages_and_save_nothing(make_survey):
    survey_id, main, _ = make_survey()
    with pytest.raises(BadMessage, match="unknown survey"):
        handle_answer(message(uuid4(), nps(main, 9)))
    with pytest.raises(BadMessage, match="not in this survey"):
        handle_answer(message(survey_id, nps(main, 9) + nps(uuid4(), 1)))
    assert stored(survey_id) == []
    assert totals(survey_id) == (0, {})


@pytest.mark.db
@needs_db
def test_a_message_cannot_write_into_another_tenants_survey(make_survey):
    survey_id, main, _ = make_survey()
    with pytest.raises(BadMessage, match="unknown survey"):
        handle_answer(message(survey_id, nps(main, 9), tenant=OTHER_TENANT))
    assert totals(survey_id) == (0, {})
