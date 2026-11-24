"""The worker saves answers and updates totals (#23).

Tests marked `db` need a migrated Postgres reached as the app role (see
survey-manager's tests); they delete the surveys they create.
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg
import pytest

from liana_survey_shared.db import ping, tenant_connection
from liana_survey_shared.messages import (
    AnswerRecorded,
    AnswerSubmitted,
    AnswerValue,
    ContactRequested,
)
from survey_worker import main as worker
from survey_worker.handlers import BadMessage, Recorded, handle_answer, parse, record_answer

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")
OTHER_TENANT = UUID("00000000-0000-4000-8000-0000000000ff")

needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)


def message(
    survey_id, answers, *, reader="reader-1", tenant=DEMO_TENANT, at=None, segment=None, **extra
) -> bytes:
    return (
        AnswerSubmitted(
            tenant_id=tenant,
            survey_id=survey_id,
            link_token_hash=f"key-{reader}",
            answers=answers,
            **({"created_at": at} if at else {}),
            **({"segment": segment} if segment else {}),
            **extra,
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


async def publish_nothing(message):
    pass


@pytest.mark.parametrize(
    ("raised", "outcome"),
    [
        (None, "ack"),
        (BadMessage("x"), ("reject", False)),  # to the dead-letter queue
        (RuntimeError("x"), ("reject", False)),
    ],
)
def test_messages_are_acked_or_dead_lettered(monkeypatch, raised, outcome):
    def fake_record(body):
        if raised:
            raise raised
        return Recorded(True)

    monkeypatch.setattr(worker, "record_answer", fake_record)
    msg = FakeMessage()
    asyncio.run(worker.process(msg, publish_nothing))
    assert msg.outcome == outcome


def test_database_outages_are_retried_not_dropped(monkeypatch):
    def fake_record(body):
        raise psycopg.OperationalError("database is down")

    monkeypatch.setattr(worker, "record_answer", fake_record)
    monkeypatch.setattr(worker, "RETRY_DELAY_SECONDS", 0)
    msg = FakeMessage()
    asyncio.run(worker.process(msg, publish_nothing))
    assert msg.outcome == ("nack", True)


# --- With a database --------------------------------------------------------------


@pytest.fixture
def make_survey():
    """Creates surveys for the demo tenant and deletes them afterwards."""
    made: list[UUID] = []

    def create(
        kind: str = "nps", survey_type: str = "nps", *, closes_at=None, response_limit=None
    ) -> tuple[UUID, UUID, UUID]:
        with tenant_connection(DEMO_TENANT) as conn:
            survey_id = conn.execute(
                """insert into surveys (tenant_id, title, type, closes_at, response_limit)
                   values (%s, 'Worker test', %s, %s, %s) returning id""",
                (DEMO_TENANT, survey_type, closes_at, response_limit),
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
def test_the_worker_stores_the_segment(make_survey):
    survey_id, main, _ = make_survey()
    assert handle_answer(message(survey_id, nps(main, 9), reader="a", segment="members")) is True
    assert handle_answer(message(survey_id, nps(main, 7), reader="b")) is True
    with tenant_connection(DEMO_TENANT) as conn:
        rows = conn.execute(
            "select segment from responses where survey_id = %s order by segment", (survey_id,)
        ).fetchall()
    assert rows == [("all",), ("members",)]


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
def test_a_readers_later_answer_replaces_the_earlier_one(make_survey):
    survey_id, main, reasons = make_survey()
    handle_answer(
        message(
            survey_id,
            nps(main, 3) + [AnswerValue(question_id=reasons, choices=["Price"])],
            reader="anna",
        )
    )
    handle_answer(message(survey_id, nps(main, 7), reader="ben"))
    # A new message (new message_id) for the same link: still one response, now 9.
    assert handle_answer(message(survey_id, nps(main, 9), reader="anna")) is True
    assert totals(survey_id) == (2, {"7": 1, "9": 1})
    assert stored(survey_id) == [(DEMO_TENANT, 7, None), (DEMO_TENANT, 9, None)]


@pytest.mark.db
@needs_db
def test_a_scanner_opening_every_link_does_not_beat_the_readers_tap(make_survey):
    survey_id, main, _ = make_survey()
    delivered = datetime.now(UTC)
    # A mail scanner opens all 11 answer links on delivery, within a second.
    for score in range(11):
        handle_answer(
            message(
                survey_id,
                nps(main, score),
                reader="anna",
                at=delivered + timedelta(milliseconds=score * 50),
            )
        )
    assert totals(survey_id) == (1, {"10": 1})
    # Anna taps 9 when she reads the email.
    handle_answer(
        message(survey_id, nps(main, 9), reader="anna", at=delivered + timedelta(hours=2))
    )
    assert totals(survey_id) == (1, {"9": 1})
    assert stored(survey_id) == [(DEMO_TENANT, 9, None)]


@pytest.mark.db
@needs_db
def test_an_older_answer_arriving_late_does_not_replace_a_newer_one(make_survey):
    survey_id, main, _ = make_survey()
    now = datetime.now(UTC)
    handle_answer(message(survey_id, nps(main, 9), reader="anna", at=now))
    # Queued earlier, delivered later (e.g. retried after a database outage).
    assert (
        handle_answer(
            message(survey_id, nps(main, 2), reader="anna", at=now - timedelta(minutes=1))
        )
        is False
    )
    assert totals(survey_id) == (1, {"9": 1})


@pytest.mark.db
@needs_db
def test_tapping_the_same_answer_again_changes_nothing_in_the_totals(make_survey):
    survey_id, main, _ = make_survey()
    handle_answer(message(survey_id, nps(main, 9), reader="anna"))
    handle_answer(message(survey_id, nps(main, 9), reader="anna"))
    assert totals(survey_id) == (1, {"9": 1})


@pytest.mark.db
@needs_db
def test_custom_surveys_replace_answers_without_a_scale(make_survey):
    survey_id, main, _ = make_survey("single_choice", "custom")
    handle_answer(
        message(survey_id, [AnswerValue(question_id=main, choices=["Yes"])], reader="anna")
    )
    handle_answer(
        message(survey_id, [AnswerValue(question_id=main, choices=["No"])], reader="anna")
    )
    assert totals(survey_id) == (1, {})
    assert stored(survey_id) == [(DEMO_TENANT, None, ["No"])]


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


@pytest.mark.db
@needs_db
def test_answers_tapped_from_the_close_date_on_are_not_saved(make_survey):
    closes = datetime.now(UTC)
    survey_id, main, _ = make_survey(closes_at=closes)
    before = closes - timedelta(seconds=1)
    assert handle_answer(message(survey_id, nps(main, 9), reader="anna", at=before)) is True
    # Queued before the close and saved late: still counts (the tap time decides).
    assert handle_answer(message(survey_id, nps(main, 7), reader="ben", at=before)) is True
    # Tapped on or after the close: neither new readers nor changed answers.
    assert handle_answer(message(survey_id, nps(main, 3), reader="cleo", at=closes)) is False
    later = closes + timedelta(hours=1)
    assert handle_answer(message(survey_id, nps(main, 0), reader="anna", at=later)) is False
    assert totals(survey_id) == (2, {"9": 1, "7": 1})


@pytest.mark.db
@needs_db
def test_a_full_survey_takes_no_new_readers_but_answers_can_still_change(make_survey):
    survey_id, main, _ = make_survey(response_limit=2)
    assert handle_answer(message(survey_id, nps(main, 9), reader="anna")) is True
    assert handle_answer(message(survey_id, nps(main, 8), reader="ben")) is True
    assert handle_answer(message(survey_id, nps(main, 3), reader="cleo")) is False
    assert handle_answer(message(survey_id, nps(main, 10), reader="anna")) is True
    assert totals(survey_id) == (2, {"10": 1, "8": 1})
    assert [row[1] for row in stored(survey_id)] == [8, 10]


@pytest.mark.db
@needs_db
def test_readers_answering_at_the_same_time_never_go_past_the_limit(make_survey):
    survey_id, main, _ = make_survey(response_limit=3)
    bodies = [message(survey_id, nps(main, 9), reader=f"r{n}") for n in range(12)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        saved = list(pool.map(handle_answer, bodies))
    assert saved.count(True) == 3
    assert totals(survey_id) == (3, {"9": 3})
    assert len(stored(survey_id)) == 3


# --- Comments, "Contact me" and events for the connector (demo review) --------------


def response_row(survey_id):
    with tenant_connection(DEMO_TENANT) as conn:
        return conn.execute(
            "select id, contact_ref, comment from responses where survey_id = %s", (survey_id,)
        ).fetchone()


def contact_requests(survey_id):
    with tenant_connection(DEMO_TENANT) as conn:
        return conn.execute(
            "select response_id, contact_ref from contact_requests where survey_id = %s",
            (survey_id,),
        ).fetchall()


def test_published_events_are_passed_on_after_the_answer_is_saved(monkeypatch):
    event = object()
    monkeypatch.setattr(worker, "record_answer", lambda body: Recorded(True, None, (event,)))
    published = []

    async def publish(message):
        published.append(message)

    msg = FakeMessage()
    asyncio.run(worker.process(msg, publish))
    assert published == [event] and msg.outcome == "ack"


@pytest.mark.db
@needs_db
def test_the_comment_is_saved_and_kept_when_the_reader_taps_again(make_survey):
    survey_id, main, _ = make_survey()
    now = datetime.now(UTC)
    record_answer(message(survey_id, nps(main, 3), at=now, comment="Too many emails"))
    record_answer(message(survey_id, nps(main, 4), at=now + timedelta(seconds=1)))
    _, _, comment = response_row(survey_id)
    assert comment == "Too many emails"


@pytest.mark.db
@needs_db
def test_contact_me_creates_one_contact_request_per_response(make_survey):
    survey_id, main, _ = make_survey()
    now = datetime.now(UTC)
    tapped = record_answer(message(survey_id, nps(main, 3), at=now))
    [recorded] = tapped.events
    assert isinstance(recorded, AnswerRecorded) and recorded.contact_ref is None
    assert contact_requests(survey_id) == []

    sent = record_answer(
        message(
            survey_id,
            nps(main, 3),
            at=now + timedelta(seconds=1),
            contact_ref="4084400",
            contact_me=True,
            campaign="november",
        )
    )
    recorded, request = sent.events
    response_id, contact_ref, _ = response_row(survey_id)
    assert isinstance(request, ContactRequested) and request.contact_ref == "4084400"
    assert contact_requests(survey_id) == [(response_id, "4084400")]
    assert (recorded.response_id, recorded.contact_ref, recorded.score, recorded.main_kind) == (
        response_id,
        "4084400",
        3,
        "nps",
    )
    assert (recorded.campaign, recorded.survey_title) == ("november", "Worker test")

    # Sent again (e.g. the form twice): still one request, none published again.
    again = record_answer(
        message(
            survey_id,
            nps(main, 3),
            at=now + timedelta(seconds=2),
            contact_ref="4084400",
            contact_me=True,
        )
    )
    assert [type(e) for e in again.events] == [AnswerRecorded]
    assert len(contact_requests(survey_id)) == 1


@pytest.mark.db
@needs_db
def test_an_identified_answer_without_contact_me_makes_no_contact_request(make_survey):
    survey_id, main, _ = make_survey()
    recorded = record_answer(message(survey_id, nps(main, 9), contact_ref="4084399"))
    [event] = recorded.events
    assert event.contact_ref == "4084399" and event.score == 9
    assert contact_requests(survey_id) == []


@pytest.mark.db
@needs_db
def test_nothing_is_passed_on_when_nothing_changed(make_survey):
    survey_id, main, _ = make_survey()
    body = message(survey_id, nps(main, 9))
    assert len(record_answer(body).events) == 1
    assert record_answer(body).events == ()  # the same message again: kept
