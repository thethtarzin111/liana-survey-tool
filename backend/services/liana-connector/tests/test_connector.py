from uuid import uuid4

import pytest

from liana_connector.adapters.mock.adapter import MockContactEvents
from liana_connector.adapters.mock.mail import MockNotificationMail
from liana_connector.factory import build_contact_events, build_notification_mail
from liana_connector.handlers import BadMessage, handle_event
from liana_connector.notifications import new_responses_email
from liana_connector.retry import backoff_seconds
from liana_survey_shared.config import Settings
from liana_survey_shared.messages import ContactRequested, NewResponsesDigest


def test_mock_adapter_records_events():
    events = MockContactEvents()
    e = ContactRequested(
        tenant_id=uuid4(), survey_id=uuid4(), contact_request_id=uuid4(), contact_ref="c1"
    )
    events.send_contact_requested(e)
    assert events.sent == [e]


def test_factory_defaults_to_mock():
    assert isinstance(build_contact_events(Settings(liana_adapter="mock")), MockContactEvents)


def test_factory_rejects_unknown_adapter():
    with pytest.raises(ValueError):
        build_contact_events(Settings(liana_adapter="nope"))


def test_backoff_grows_and_is_capped():
    assert [backoff_seconds(n) for n in (1, 2, 3)] == [2, 4, 8]
    assert backoff_seconds(20) == 300


# --- "New responses" emails -------------------------------------------------------


def a_digest(**changes) -> NewResponsesDigest:
    fields = {
        "tenant_id": uuid4(),
        "survey_id": uuid4(),
        "survey_title": "Member satisfaction 2026",
        "new_responses": 3,
        "total_responses": 40,
        "results_url": "http://localhost:4200/results?survey=1",
        "recipient_email": "anna.virtanen@example.org",
        "recipient_name": "Anna Virtanen",
    }
    return NewResponsesDigest(**{**fields, **changes})


def test_a_digest_message_is_sent_through_the_mail_port():
    contacts, mail = MockContactEvents(), MockNotificationMail()
    handle_event(a_digest().model_dump_json().encode(), contacts, mail)
    [email] = mail.sent
    assert email.to_address == "anna.virtanen@example.org"
    assert email.subject == "Member satisfaction 2026: 3 new responses"
    assert "40 responses in total" in email.text
    assert "http://localhost:4200/results?survey=1" in email.text
    assert contacts.sent == []


def test_one_new_response_reads_in_the_singular():
    email = new_responses_email(a_digest(new_responses=1, total_responses=1))
    assert email.subject == "Member satisfaction 2026: 1 new response"
    assert "(1 response in total)" in email.text


def test_contact_requests_still_go_to_liana_automation():
    contacts, mail = MockContactEvents(), MockNotificationMail()
    event = ContactRequested(
        tenant_id=uuid4(), survey_id=uuid4(), contact_request_id=uuid4(), contact_ref="c1"
    )
    handle_event(event.model_dump_json().encode(), contacts, mail)
    assert contacts.sent == [event]
    assert mail.sent == []


@pytest.mark.parametrize(
    "body", [b"not json", b'{"type": "something.else"}', b'{"type": "responses.digest"}']
)
def test_unknown_or_broken_messages_are_bad_messages(body):
    with pytest.raises(BadMessage):
        handle_event(body, MockContactEvents(), MockNotificationMail())


def test_mail_factory_defaults_to_mock_and_rejects_unknown_adapters():
    assert isinstance(build_notification_mail(Settings()), MockNotificationMail)
    with pytest.raises(ValueError):
        build_notification_mail(Settings(notification_mail_adapter="smtp"))
