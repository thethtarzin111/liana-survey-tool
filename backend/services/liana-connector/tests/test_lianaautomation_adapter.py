"""The LianaAutomation adapter: "Contact me" requests through the organisation's own
connection, with a fake client. Needs a migrated Postgres reached as the app role; each
test removes the connection and the events it made, so run them on a test database."""

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from psycopg.rows import dict_row

from liana_connector.adapters.lianaautomation.adapter import (
    DeliveryFailed,
    LianaAutomationContactEvents,
)
from liana_connector.automation import domain, repo, secrets
from liana_connector.automation.client import ConfigError, TemporaryError
from liana_connector.factory import build_contact_events
from liana_connector.ports.contact_events import TemporaryError as RetryLater
from liana_survey_shared.config import Settings
from liana_survey_shared.db import ping, tenant_connection
from liana_survey_shared.messages import ContactRequested

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")
KEY = "test-key"
needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)


class FakeClient:
    """Records each /import body; `failures` are raised first, in order."""

    def __init__(self, failures=()):
        self.failures = list(failures)
        self.imports = []

    def __call__(self, host, client_id, secret):
        assert (host, client_id, secret) == (
            "rest.automation.lianacloud.com",
            "id-1",
            "s3cret-abcd",
        )
        return self

    def import_events(self, body):
        if self.failures:
            raise self.failures.pop(0)
        self.imports.append(body)


def a_request(**changes) -> ContactRequested:
    fields = {
        "tenant_id": DEMO_TENANT,
        "survey_id": uuid4(),
        "contact_request_id": uuid4(),
        "contact_ref": "C-1100",
        "created_at": datetime(2026, 11, 24, 12, 0, tzinfo=UTC),
    }
    return ContactRequested(**{**fields, **changes})


def _clean():
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("delete from integrations")
        conn.execute("delete from integration_events where verb = 'survey_contact_request'")


@pytest.fixture
def connect():
    """Saves a connection for the demo organisation: connected, channel 7, by default."""
    _clean()

    def save(status="connected", channel_id="7", **settings):
        with tenant_connection(DEMO_TENANT) as conn:
            conn.row_factory = dict_row
            repo.save_credentials(
                conn,
                DEMO_TENANT,
                "rest.automation.lianacloud.com",
                "id-1",
                secrets.encrypt("s3cret-abcd", KEY),
                "abcd",
                domain.merged_settings(None, settings),
            )
            repo.update(conn, status=status, channel_id=channel_id)

    yield save
    _clean()


def _log():
    with tenant_connection(DEMO_TENANT) as conn:
        conn.row_factory = dict_row
        return repo.events(conn, None, 50), repo.get(conn)


def test_the_event_identifies_the_contact_by_its_id_not_an_email():
    event = domain.contact_request_event("C-1100", "s1", "r1", datetime(2026, 11, 24, tzinfo=UTC))
    assert event == {
        "identity": {"lianamailer_id": "C-1100"},
        "events": [
            {
                "verb": "survey_contact_request",
                "items": {
                    "survey_id": "s1",
                    "contact_request_id": "r1",
                    "requested_at": "2026-11-24T00:00:00+00:00",
                },
            }
        ],
    }
    assert domain.masked_email(domain.contact_of(event)) == "C-…"


def test_the_factory_builds_the_adapter_from_the_secret_key():
    adapter = build_contact_events(
        Settings(liana_adapter="lianaautomation", integration_secret_key=KEY)
    )
    assert isinstance(adapter, LianaAutomationContactEvents) and adapter.secret_key == KEY
    with pytest.raises(secrets.WeakKey):  # the repo's default key, outside dev mode
        build_contact_events(
            Settings(
                liana_adapter="lianaautomation",
                auth_mode="oidc",
                integration_secret_key=secrets.DEV_KEY,
            )
        )


@needs_db
def test_a_demo_connection_is_refused_outside_dev_mode(connect):
    connect()
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("update integrations set host = 'demo'")
    with pytest.raises(DeliveryFailed):
        LianaAutomationContactEvents(KEY, allow_demo=False).send_contact_requested(a_request())
    [row], connection = _log()
    assert row["status"] == "failed" and "local development" in row["last_error"]
    assert connection["status"] == "error"


@needs_db
def test_nothing_is_sent_without_a_connection_or_with_the_switch_off(connect):
    _clean()
    fake = FakeClient()
    LianaAutomationContactEvents(KEY, build=fake).send_contact_requested(a_request())
    connect(contact_requests=False)
    LianaAutomationContactEvents(KEY, build=fake).send_contact_requested(a_request())
    assert fake.imports == [] and _log()[0] == []


@needs_db
def test_a_request_is_sent_once_and_logged(connect):
    connect()
    fake = FakeClient()
    adapter = LianaAutomationContactEvents(KEY, build=fake)
    request = a_request()
    adapter.send_contact_requested(request)
    adapter.send_contact_requested(request)  # redelivered: not sent twice

    [body] = fake.imports
    assert body["channel"] == "7" and body["no_duplicates"] is True
    assert body["data"][0]["identity"] == {"lianamailer_id": "C-1100"}
    [row], _ = _log()
    assert (row["verb"], row["status"], row["attempts"], row["test"]) == (
        "survey_contact_request",
        "sent",
        1,
        False,
    )


@needs_db
def test_an_untested_connection_logs_a_failed_event_to_retry_later(connect):
    connect(status="disconnected")
    fake = FakeClient()
    LianaAutomationContactEvents(KEY, build=fake).send_contact_requested(a_request())
    [row], _ = _log()
    assert row["status"] == "failed" and "Test the connection" in row["last_error"]
    assert fake.imports == []


@needs_db
def test_a_temporary_error_is_retried_on_the_same_row(connect):
    connect()
    fake = FakeClient(failures=[TemporaryError("Liana answered 503. Try again later.")])
    adapter = LianaAutomationContactEvents(KEY, build=fake)
    request = a_request()
    with pytest.raises(RetryLater):
        adapter.send_contact_requested(request)
    [row], _ = _log()
    assert (row["status"], row["attempts"]) == ("retrying", 1)

    adapter.send_contact_requested(request)
    [row], _ = _log()
    assert (row["status"], row["attempts"], row["last_error"]) == ("sent", 2, None)
    assert len(fake.imports) == 1


@needs_db
def test_a_wrong_host_fails_and_marks_the_connection(connect):
    connect()
    fake = FakeClient(failures=[ConfigError("Not found (404): check the host.")])
    with pytest.raises(DeliveryFailed):
        LianaAutomationContactEvents(KEY, build=fake).send_contact_requested(a_request())
    [row], connection = _log()
    assert row["status"] == "failed"
    assert (connection["status"], connection["last_error"]) == (
        "error",
        "Not found (404): check the host.",
    )
