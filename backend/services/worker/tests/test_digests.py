"""The "new responses" emails to a survey's owner: the first new response is
emailed at once, later ones within the interval are held and sent as one digest.

Tests marked `db` need a migrated Postgres reached as the app role (see
test_handlers.py); they delete the surveys they create.
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from liana_survey_shared.db import due_response_digests, ping, tenant_connection
from liana_survey_shared.messages import AnswerSubmitted, AnswerValue, NewResponsesDigest
from survey_worker import digests
from survey_worker import main as worker
from survey_worker.domain import digest, new_responses_due
from survey_worker.handlers import Recorded, record_answer

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")
DEMO_USER = UUID("00000000-0000-4000-8000-000000000101")
HOUR = timedelta(hours=1)
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)

needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)


# --- The rules, without a database ------------------------------------------------


def test_the_first_new_response_is_emailed_at_once():
    due = new_responses_due(total=1, notified_count=0, last_sent_at=None, now=NOW, interval=HOUR)
    assert due == 1


def test_responses_within_the_interval_are_held():
    last = NOW - timedelta(minutes=59)
    assert (
        new_responses_due(total=5, notified_count=1, last_sent_at=last, now=NOW, interval=HOUR) == 0
    )


def test_held_responses_are_sent_as_one_digest_once_the_interval_has_passed():
    last = NOW - HOUR
    assert (
        new_responses_due(total=5, notified_count=1, last_sent_at=last, now=NOW, interval=HOUR) == 4
    )


def test_no_new_responses_means_no_email():
    long_ago = NOW - timedelta(days=3)
    assert (
        new_responses_due(total=5, notified_count=5, last_sent_at=long_ago, now=NOW, interval=HOUR)
        == 0
    )


def test_the_message_has_counts_and_a_link_but_no_answers():
    survey_id = uuid4()
    message = digest(
        tenant_id=DEMO_TENANT,
        survey_id=survey_id,
        survey_title="Member satisfaction 2026",
        new_responses=3,
        total_responses=40,
        app_base_url="http://localhost:4200/",
        recipient_email="anna.virtanen@example.org",
        recipient_name="Anna Virtanen",
    )
    assert message.results_url == f"http://localhost:4200/results?survey={survey_id}"
    assert set(message.model_dump()) == {
        "message_id",
        "created_at",
        "tenant_id",
        "type",
        "survey_id",
        "survey_title",
        "new_responses",
        "total_responses",
        "results_url",
        "recipient_email",
        "recipient_name",
    }


class FakeMessage:
    body = b"{}"
    outcome = None

    async def ack(self):
        self.outcome = "ack"

    async def reject(self, requeue):
        self.outcome = ("reject", requeue)


def a_digest() -> NewResponsesDigest:
    return digest(
        tenant_id=DEMO_TENANT,
        survey_id=uuid4(),
        survey_title="Poll",
        new_responses=1,
        total_responses=1,
        app_base_url="http://localhost:4200",
        recipient_email="anna.virtanen@example.org",
        recipient_name="Anna Virtanen",
    )


def test_the_worker_publishes_a_due_email_and_acks_the_answer(monkeypatch):
    due = a_digest()
    monkeypatch.setattr(worker, "record_answer", lambda body: Recorded(True, due))
    published = []

    async def publish(message):
        published.append(message)

    msg = FakeMessage()
    asyncio.run(worker.process(msg, publish))
    assert published == [due]
    assert msg.outcome == "ack"


def test_a_failed_email_publish_does_not_lose_the_saved_answer(monkeypatch):
    monkeypatch.setattr(worker, "record_answer", lambda body: Recorded(True, a_digest()))

    async def publish(message):
        raise ConnectionError("RabbitMQ is down")

    msg = FakeMessage()
    asyncio.run(worker.process(msg, publish))
    assert msg.outcome == "ack"


# --- With a database --------------------------------------------------------------


@pytest.fixture
def make_survey():
    """Creates one-question surveys for the demo tenant and deletes them afterwards."""
    made: list[UUID] = []

    def create(*, notify: bool = True, owner: UUID | None = DEMO_USER) -> tuple[UUID, UUID]:
        with tenant_connection(DEMO_TENANT) as conn:
            survey_id = conn.execute(
                """insert into surveys (tenant_id, title, type, notify_on_response, created_by)
                   values (%s, 'Digest test', 'nps', %s, %s) returning id""",
                (DEMO_TENANT, notify, owner),
            ).fetchone()[0]
            question = conn.execute(
                """insert into questions (tenant_id, survey_id, position, kind, prompt)
                   values (%s, %s, 1, 'nps', 'Main?') returning id""",
                (DEMO_TENANT, survey_id),
            ).fetchone()[0]
        made.append(survey_id)
        return survey_id, question

    yield create
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("delete from surveys where id = any(%s)", (made,))


def answer(survey_id, question, reader, score=9, text=None) -> bytes:
    answers = [AnswerValue(question_id=question, number=score, text=text)]
    return (
        AnswerSubmitted(
            tenant_id=DEMO_TENANT,
            survey_id=survey_id,
            link_token_hash=f"key-{reader}",
            answers=answers,
        )
        .model_dump_json()
        .encode()
    )


def last_email_was_ago(survey_id, delta: timedelta) -> None:
    """Pretend the last email went out `delta` ago."""
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute(
            "update response_notifications set last_sent_at = now() - %s where survey_id = %s",
            (delta, survey_id),
        )


def sweep() -> list[NewResponsesDigest]:
    sent: list[NewResponsesDigest] = []

    async def publish(message):
        sent.append(message)

    asyncio.run(digests.sweep_once(publish, HOUR))
    return sent


@pytest.mark.db
@needs_db
def test_first_response_now_then_one_digest_after_the_interval(make_survey):
    survey_id, question = make_survey()
    first = record_answer(answer(survey_id, question, "anna"))
    assert first.digest is not None
    assert (first.digest.new_responses, first.digest.total_responses) == (1, 1)
    assert first.digest.recipient_email == "anna.virtanen@example.org"
    assert first.digest.survey_id == survey_id

    # Within the interval: held, and the sweep does not send them yet.
    held = [record_answer(answer(survey_id, question, r)).digest for r in ("ben", "cleo")]
    assert held == [None, None]
    assert sweep() == []

    last_email_was_ago(survey_id, HOUR)
    [sent] = [d for d in sweep() if d.survey_id == survey_id]
    assert (sent.new_responses, sent.total_responses) == (2, 3)
    # Claimed: the next sweep sends nothing.
    assert [d for d in sweep() if d.survey_id == survey_id] == []


@pytest.mark.db
@needs_db
def test_a_new_response_after_the_interval_is_emailed_at_once(make_survey):
    survey_id, question = make_survey()
    record_answer(answer(survey_id, question, "anna"))
    record_answer(answer(survey_id, question, "ben"))
    last_email_was_ago(survey_id, 2 * HOUR)
    later = record_answer(answer(survey_id, question, "cleo")).digest
    assert later is not None
    assert (later.new_responses, later.total_responses) == (2, 3)


@pytest.mark.db
@needs_db
def test_nothing_is_sent_without_new_responses(make_survey):
    survey_id, question = make_survey()
    record_answer(answer(survey_id, question, "anna"))
    last_email_was_ago(survey_id, 2 * HOUR)
    # A changed answer is not a new response.
    assert record_answer(answer(survey_id, question, "anna", score=3)).digest is None
    assert [d for d in sweep() if d.survey_id == survey_id] == []


@pytest.mark.db
@needs_db
def test_no_email_when_notify_is_off(make_survey):
    survey_id, question = make_survey(notify=False)
    recorded = record_answer(answer(survey_id, question, "anna"))
    assert recorded.changed is True
    assert recorded.digest is None


@pytest.mark.db
@needs_db
def test_turning_notify_off_drops_held_responses(make_survey):
    survey_id, question = make_survey()
    record_answer(answer(survey_id, question, "anna"))
    record_answer(answer(survey_id, question, "ben"))
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("update surveys set notify_on_response = false where id = %s", (survey_id,))
    record_answer(answer(survey_id, question, "cleo"))
    with tenant_connection(DEMO_TENANT) as conn:
        assert (
            conn.execute(
                "select count(*) from response_notifications where survey_id = %s", (survey_id,)
            ).fetchone()[0]
            == 0
        )


@pytest.mark.db
@needs_db
def test_the_email_never_carries_answers(make_survey):
    survey_id, question = make_survey()
    recorded = record_answer(answer(survey_id, question, "anna", text="Secret comment"))
    assert recorded.digest is not None
    assert "Secret comment" not in recorded.digest.model_dump_json()


@pytest.mark.db
@needs_db
def test_two_workers_claiming_the_same_digest_send_it_once(make_survey):
    survey_id, question = make_survey()
    record_answer(answer(survey_id, question, "anna"))
    record_answer(answer(survey_id, question, "ben"))
    last_email_was_ago(survey_id, HOUR)
    with ThreadPoolExecutor(max_workers=6) as pool:
        claimed = list(
            pool.map(lambda _: digests.claim_due(DEMO_TENANT, survey_id, HOUR), range(6))
        )
    sent = [d for d in claimed if d is not None]
    assert [d.new_responses for d in sent] == [1]


@pytest.mark.db
@needs_db
def test_the_sweep_finds_due_surveys_without_a_tenant(make_survey):
    survey_id, question = make_survey()
    record_answer(answer(survey_id, question, "anna"))
    record_answer(answer(survey_id, question, "ben"))
    assert (survey_id, DEMO_TENANT) not in due_response_digests(3600)
    last_email_was_ago(survey_id, HOUR)
    assert (survey_id, DEMO_TENANT) in due_response_digests(3600)
