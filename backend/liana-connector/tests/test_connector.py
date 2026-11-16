from uuid import uuid4

import pytest

from liana_connector.adapters.mock.adapter import MockContactEvents
from liana_connector.factory import build_contact_events
from liana_connector.retry import backoff_seconds
from liana_survey_shared.config import Settings
from liana_survey_shared.messages import ContactRequested


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
