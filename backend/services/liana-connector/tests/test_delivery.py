"""Contact requests reach LianaAutomation through the ContactEvents port (#58):
temporary errors are retried with back-off, and after MAX_ATTEMPTS the message
goes to the dead-letter queue. The result is stored on the contact request.

Tests marked `db` need a migrated Postgres reached as the app role.
"""

import asyncio
import os
from uuid import UUID, uuid4

import pytest

from liana_connector import main as connector
from liana_connector.adapters.mock.adapter import MockContactEvents
from liana_connector.adapters.mock.mail import MockNotificationMail
from liana_connector.delivery_status import record_contact_request_status
from liana_connector.handlers import Outcome, deliver
from liana_connector.ports.contact_events import TemporaryError
from liana_connector.retry import MAX_ATTEMPTS
from liana_survey_shared.db import ping, tenant_connection
from liana_survey_shared.messages import ContactRequested, NewResponsesDigest

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")

needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)


class FailingContacts:
    """LianaAutomation that fails the same way every time."""

    def __init__(self, error: Exception):
        self.error = error
        self.calls = 0

    def send_contact_requested(self, event):
        self.calls += 1
        raise self.error


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, event, status, attempts):
        self.calls.append((event.contact_request_id, status, attempts))


def a_request(**changes) -> ContactRequested:
    fields = {
        "tenant_id": DEMO_TENANT,
        "survey_id": uuid4(),
        "contact_request_id": uuid4(),
        "contact_ref": "member-1042",
    }
    return ContactRequested(**{**fields, **changes})


def body(event) -> bytes:
    return event.model_dump_json().encode()


def test_a_delivered_request_is_acked_and_marked_sent():
    event, contacts, record = a_request(), MockContactEvents(), Recorder()
    outcome = deliver(body(event), 1, contacts, MockNotificationMail(), record)
    assert outcome == Outcome("ack")
    assert contacts.sent == [event]
    assert record.calls == [(event.contact_request_id, "sent", 1)]


def test_a_temporary_error_is_retried_with_back_off_and_stays_pending():
    event, record = a_request(), Recorder()
    contacts = FailingContacts(TemporaryError("503"))
    first = deliver(body(event), 1, contacts, MockNotificationMail(), record)
    third = deliver(body(event), 3, contacts, MockNotificationMail(), record)
    assert first == Outcome("retry", 2)
    assert third == Outcome("retry", 8)
    assert record.calls == [
        (event.contact_request_id, "pending", 1),
        (event.contact_request_id, "pending", 3),
    ]


def test_after_the_last_attempt_the_request_is_dead_lettered_and_marked_failed():
    event, record = a_request(), Recorder()
    outcome = deliver(
        body(event),
        MAX_ATTEMPTS,
        FailingContacts(TemporaryError("503")),
        MockNotificationMail(),
        record,
    )
    assert outcome == Outcome("dead")
    assert record.calls == [(event.contact_request_id, "failed", MAX_ATTEMPTS)]


def test_an_error_that_retrying_cannot_fix_is_dead_lettered_at_once():
    event, record = a_request(), Recorder()
    contacts = FailingContacts(NotImplementedError("adapter not built"))
    outcome = deliver(body(event), 1, contacts, MockNotificationMail(), record)
    assert outcome == Outcome("dead")
    assert contacts.calls == 1
    assert record.calls == [(event.contact_request_id, "failed", 1)]


def test_a_broken_message_is_dead_lettered_without_a_status():
    record = Recorder()
    outcome = deliver(b"not json", 1, MockContactEvents(), MockNotificationMail(), record)
    assert outcome == Outcome("dead")
    assert record.calls == []


def test_a_status_that_cannot_be_stored_does_not_undo_the_delivery():
    def broken_record(event, status, attempts):
        raise RuntimeError("database is down")

    contacts = MockContactEvents()
    outcome = deliver(body(a_request()), 1, contacts, MockNotificationMail(), broken_record)
    assert outcome == Outcome("ack")
    assert len(contacts.sent) == 1


def test_new_responses_emails_are_retried_too_but_have_no_status():
    class FailingMail:
        def send(self, email):
            raise TemporaryError("smtp down")

    digest = NewResponsesDigest(
        tenant_id=DEMO_TENANT,
        survey_id=uuid4(),
        survey_title="Member satisfaction 2026",
        new_responses=1,
        total_responses=1,
        results_url="http://localhost:4200/results",
        recipient_email="anna.virtanen@example.org",
        recipient_name="Anna Virtanen",
    )
    record = Recorder()
    outcome = deliver(body(digest), 1, MockContactEvents(), FailingMail(), record)
    assert outcome == Outcome("retry", 2)
    assert record.calls == []


# --- The RabbitMQ side, with fakes --------------------------------------------------


class FakeExchange:
    def __init__(self):
        self.published = []

    async def publish(self, message, routing_key):
        self.published.append((message, routing_key))


class FakeChannel:
    def __init__(self):
        self.default_exchange = FakeExchange()


class FakeMessage:
    def __init__(self, body, headers=None):
        self.body = body
        self.headers = headers
        self.content_type = "application/json"
        self.message_id = "m-1"
        self.outcome = None

    async def ack(self):
        self.outcome = "ack"

    async def reject(self, requeue):
        self.outcome = ("reject", requeue)

    async def nack(self, requeue):
        self.outcome = ("nack", requeue)


def run_process(message, contacts):
    channel = FakeChannel()

    async def go():
        pending: set[asyncio.Task] = set()
        await connector.process(
            channel, message, contacts, MockNotificationMail(), Recorder(), pending
        )
        await asyncio.gather(*pending)

    asyncio.run(go())
    return channel.default_exchange.published


def test_a_retry_is_published_with_the_next_attempt_before_the_original_is_acked(monkeypatch):
    monkeypatch.setattr("liana_connector.handlers.backoff_seconds", lambda attempt: 0)
    message = FakeMessage(body(a_request()), headers={connector.ATTEMPT_HEADER: 2})
    published = run_process(message, FailingContacts(TemporaryError("503")))
    [(copy, routing_key)] = published
    assert routing_key == "survey.liana-events"
    assert copy.headers[connector.ATTEMPT_HEADER] == 3
    assert copy.body == message.body
    assert message.outcome == "ack"


def test_a_message_without_an_attempt_header_is_the_first_attempt():
    assert connector.attempt_of(FakeMessage(b"{}")) == 1
    assert connector.attempt_of(FakeMessage(b"{}", {connector.ATTEMPT_HEADER: "x"})) == 1


@pytest.mark.parametrize(
    ("contacts", "outcome"),
    [
        (MockContactEvents(), "ack"),
        (FailingContacts(NotImplementedError()), ("reject", False)),  # to the dead-letter queue
    ],
)
def test_delivered_messages_are_acked_and_failed_ones_dead_lettered(contacts, outcome):
    message = FakeMessage(body(a_request()))
    assert run_process(message, contacts) == []
    assert message.outcome == outcome


# --- With a database --------------------------------------------------------------


@pytest.fixture
def contact_request():
    """A survey with one response and its contact request, deleted afterwards."""
    with tenant_connection(DEMO_TENANT) as conn:
        survey_id = conn.execute(
            """insert into surveys (tenant_id, title, type)
               values (%s, 'Connector test', 'nps') returning id""",
            (DEMO_TENANT,),
        ).fetchone()[0]
        response_id = conn.execute(
            """insert into responses (tenant_id, survey_id, link_token_hash, contact_ref)
               values (%s, %s, 'key-connector', 'member-1042') returning id""",
            (DEMO_TENANT, survey_id),
        ).fetchone()[0]
        request_id = conn.execute(
            """insert into contact_requests (tenant_id, survey_id, response_id, contact_ref)
               values (%s, %s, %s, 'member-1042') returning id""",
            (DEMO_TENANT, survey_id, response_id),
        ).fetchone()[0]
    yield a_request(survey_id=survey_id, contact_request_id=request_id)
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("delete from surveys where id = %s", (survey_id,))


def stored_status(request_id):
    with tenant_connection(DEMO_TENANT) as conn:
        return conn.execute(
            """select liana_status, liana_attempts, liana_updated_at is not null
               from contact_requests where id = %s""",
            (request_id,),
        ).fetchone()


@pytest.mark.db
@needs_db
def test_a_new_contact_request_is_pending(contact_request):
    assert stored_status(contact_request.contact_request_id) == ("pending", 0, False)


@pytest.mark.db
@needs_db
def test_the_result_is_stored_on_the_contact_request(contact_request):
    record_contact_request_status(contact_request, "failed", 8)
    assert stored_status(contact_request.contact_request_id) == ("failed", 8, True)


@pytest.mark.db
@needs_db
def test_another_tenant_cannot_change_the_status(contact_request):
    other = contact_request.model_copy(
        update={"tenant_id": UUID("00000000-0000-4000-8000-0000000000ff")}
    )
    record_contact_request_status(other, "sent", 1)
    assert stored_status(contact_request.contact_request_id) == ("pending", 0, False)


# --- "You said, we did" replies (#63) -----------------------------------------------


def a_reply(**changes):
    from liana_survey_shared.messages import ContactResolved

    fields = {
        "tenant_id": DEMO_TENANT,
        "survey_id": uuid4(),
        "contact_request_id": uuid4(),
        "contact_ref": "member-1042",
        "message": "You said the events start too late. From January they start at 17.",
    }
    return ContactResolved(**{**fields, **changes})


def test_a_reply_goes_to_the_reader_through_the_contact_events_port():
    event, contacts, record = a_reply(), MockContactEvents(), Recorder()
    outcome = deliver(body(event), 1, contacts, MockNotificationMail(), record)
    assert outcome == Outcome("ack")
    assert contacts.resolved == [event]
    assert contacts.sent == []
    assert record.calls == [(event.contact_request_id, "sent", 1)]


def test_a_reply_is_retried_like_a_request():
    class Down:
        def send_contact_resolved(self, event):
            raise TemporaryError("503")

    event, record = a_reply(), Recorder()
    assert deliver(body(event), 1, Down(), MockNotificationMail(), record) == Outcome("retry", 2)
    assert deliver(body(event), MAX_ATTEMPTS, Down(), MockNotificationMail(), record) == Outcome(
        "dead"
    )
    assert [status for _, status, _ in record.calls] == ["pending", "failed"]


def stored_reply(request_id):
    with tenant_connection(DEMO_TENANT) as conn:
        return conn.execute(
            "select reply_status, reply_attempts, liana_status from contact_requests where id = %s",
            (request_id,),
        ).fetchone()


@pytest.mark.db
@needs_db
def test_a_replys_result_is_stored_apart_from_the_requests(contact_request):
    reply = a_reply(
        survey_id=contact_request.survey_id,
        contact_request_id=contact_request.contact_request_id,
    )
    record_contact_request_status(reply, "sent", 2)
    assert stored_reply(contact_request.contact_request_id) == ("sent", 2, "pending")
