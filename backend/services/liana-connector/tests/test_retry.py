"""The connector retries temporary errors with back-off (#58): the message is
published again with the next attempt number, and after MAX_ATTEMPTS it goes to the
dead-letter queue and the port records the event as failed (Retry in the sync log)."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from liana_connector import main as connector
from liana_connector.adapters.mock.adapter import MockContactEvents
from liana_connector.adapters.mock.mail import MockNotificationMail
from liana_connector.handlers import Outcome, deliver
from liana_connector.ports.contact_events import TemporaryError
from liana_connector.retry import MAX_ATTEMPTS
from liana_survey_shared.messages import AnswerRecorded, ContactRequested, NewResponsesDigest

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")


class Down(MockContactEvents):
    """LianaAutomation that fails the same way every time."""

    def __init__(self, error: Exception):
        super().__init__()
        self.error = error
        self.calls = 0

    def send_contact_requested(self, event):
        self.calls += 1
        raise self.error

    def send_answer_recorded(self, event):
        self.calls += 1
        raise self.error


def a_request() -> ContactRequested:
    return ContactRequested(
        tenant_id=DEMO_TENANT,
        survey_id=uuid4(),
        contact_request_id=uuid4(),
        contact_ref="C-1100",
        created_at=datetime(2026, 11, 25, 12, 0, tzinfo=UTC),
    )


def an_answer() -> AnswerRecorded:
    return AnswerRecorded(
        tenant_id=DEMO_TENANT,
        survey_id=uuid4(),
        response_id=uuid4(),
        survey_title="Member NPS",
        main_kind="nps",
        score=4,
        campaign=None,
        contact_ref="4084399",
    )


def body(event) -> bytes:
    return event.model_dump_json().encode()


def test_a_delivered_message_is_acked():
    contacts = MockContactEvents()
    assert deliver(body(a_request()), 1, contacts, MockNotificationMail()) == Outcome("ack")
    assert len(contacts.sent) == 1


@pytest.mark.parametrize("event", [a_request(), an_answer()], ids=["request", "answer"])
def test_a_temporary_error_is_retried_with_growing_delays(event):
    contacts = Down(TemporaryError("Liana answered 503."))
    first = deliver(body(event), 1, contacts, MockNotificationMail())
    third = deliver(body(event), 3, contacts, MockNotificationMail())
    assert (first, third) == (Outcome("retry", 2), Outcome("retry", 8))
    assert contacts.given_up == []


@pytest.mark.parametrize("event", [a_request(), an_answer()], ids=["request", "answer"])
def test_after_the_last_attempt_the_event_is_failed_and_dead_lettered(event):
    contacts = Down(TemporaryError("Liana answered 503."))
    outcome = deliver(body(event), MAX_ATTEMPTS, contacts, MockNotificationMail())
    assert outcome == Outcome("dead")
    [(given_up, reason)] = contacts.given_up
    assert given_up.message_id == event.message_id
    assert reason == "Liana answered 503."


def test_an_error_that_retrying_cannot_fix_is_dead_lettered_at_once():
    contacts = Down(RuntimeError("wrong credentials"))
    assert deliver(body(a_request()), 1, contacts, MockNotificationMail()) == Outcome("dead")
    assert (contacts.calls, contacts.given_up) == (1, [])


def test_a_broken_message_is_dead_lettered():
    assert deliver(b"not json", 1, MockContactEvents(), MockNotificationMail()) == Outcome("dead")


def test_a_failure_to_mark_the_event_does_not_stop_the_dead_letter():
    class CannotGiveUp(Down):
        def give_up(self, event, reason):
            raise RuntimeError("database is down")

    contacts = CannotGiveUp(TemporaryError("503"))
    assert deliver(body(a_request()), MAX_ATTEMPTS, contacts, MockNotificationMail()) == Outcome(
        "dead"
    )


def test_new_responses_emails_are_retried_too():
    class MailDown:
        def send(self, email):
            raise TemporaryError("mail server down")

    digest = NewResponsesDigest(
        tenant_id=DEMO_TENANT,
        survey_id=uuid4(),
        survey_title="Member NPS",
        new_responses=1,
        total_responses=1,
        results_url="http://localhost:4200/results",
        recipient_email="anna.virtanen@example.org",
        recipient_name="Anna Virtanen",
    )
    contacts = MockContactEvents()
    assert deliver(body(digest), 1, contacts, MailDown()) == Outcome("retry", 2)
    assert deliver(body(digest), MAX_ATTEMPTS, contacts, MailDown()) == Outcome("dead")
    assert contacts.given_up == []


# --- The RabbitMQ side, with fakes ---------------------------------------------------


class FakeExchange:
    def __init__(self, fail=False):
        self.fail = fail
        self.published = []

    async def publish(self, message, routing_key):
        if self.fail:
            raise ConnectionError("broker is down")
        self.published.append((message, routing_key))


class FakeChannel:
    def __init__(self, fail=False):
        self.default_exchange = FakeExchange(fail)


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


def run_process(message, contacts, channel=None):
    channel = channel or FakeChannel()

    async def go():
        pending: set[asyncio.Task] = set()
        await connector.process(channel, message, contacts, MockNotificationMail(), pending)
        await asyncio.gather(*pending)

    asyncio.run(go())
    return channel.default_exchange.published


def test_a_retry_is_published_with_the_next_attempt_before_the_original_is_acked(monkeypatch):
    monkeypatch.setattr("liana_connector.handlers.backoff_seconds", lambda attempt: 0)
    message = FakeMessage(body(a_request()), headers={connector.ATTEMPT_HEADER: 2})
    [(copy, routing_key)] = run_process(message, Down(TemporaryError("503")))
    assert routing_key == "survey.liana-events"
    assert copy.headers[connector.ATTEMPT_HEADER] == 3
    assert copy.body == message.body
    assert message.outcome == "ack"


def test_a_retry_that_cannot_be_published_puts_the_message_back(monkeypatch):
    monkeypatch.setattr("liana_connector.handlers.backoff_seconds", lambda attempt: 0)
    message = FakeMessage(body(a_request()))
    run_process(message, Down(TemporaryError("503")), FakeChannel(fail=True))
    assert message.outcome == ("nack", True)


@pytest.mark.parametrize(
    ("contacts", "outcome"),
    [(MockContactEvents(), "ack"), (Down(RuntimeError("bug")), ("reject", False))],
    ids=["delivered", "dead-lettered"],
)
def test_messages_are_acked_or_dead_lettered(contacts, outcome):
    message = FakeMessage(body(a_request()))
    assert run_process(message, contacts) == []
    assert message.outcome == outcome


def test_a_message_without_a_valid_attempt_header_is_the_first_attempt():
    assert connector.attempt_of(FakeMessage(b"{}")) == 1
    assert connector.attempt_of(FakeMessage(b"{}", {connector.ATTEMPT_HEADER: "x"})) == 1
