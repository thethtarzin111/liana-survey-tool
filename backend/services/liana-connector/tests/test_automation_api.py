"""The Integrations API, step by step like the wizard, with the demo LianaAutomation.
Needs a migrated Postgres reached as the app role; every test starts disconnected and
removes what it made."""

import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from liana_connector.api import app
from liana_connector.automation import repo, routes, secrets
from liana_connector.automation.client import ConfigError
from liana_connector.automation.routes import client_factory
from liana_survey_shared.config import Settings
from liana_survey_shared.db import ping, tenant_connection

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")
DEMO_USER = UUID("00000000-0000-4000-8000-000000000101")
HEADERS = {"X-Tenant-Id": str(DEMO_TENANT), "X-User-Id": str(DEMO_USER)}
pytestmark = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)
URL = "/api/v1/integrations"
DEMO = {"host": "demo", "client_id": "demo-client", "client_secret": "demo-secret"}


def _clean():
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("delete from integrations")
        conn.execute("delete from integration_events where test")


@pytest.fixture
def api():
    """A client for a tenant without a connection. Puts back nothing: a local connection
    made in the browser would be removed, so run these tests on a test database."""
    _clean()
    yield TestClient(app, headers=HEADERS)
    app.dependency_overrides.clear()
    _clean()


def test_the_wizard_from_credentials_to_test_event(api):
    assert api.get(URL).json()["liana_automation"] is None

    # 1. Credentials: the secret is stored encrypted and never returned.
    saved = api.put(f"{URL}/liana-automation", json=DEMO)
    assert saved.status_code == 200
    body = saved.json()
    assert body["status"] == "disconnected" and body["secret_hint"] == "cret"
    assert "demo-secret" not in saved.text
    with tenant_connection(DEMO_TENANT) as conn:
        stored = conn.execute("select secret_encrypted from integrations").fetchone()[0]
    assert b"demo-secret" not in bytes(stored)

    # 2. Test connection.
    assert api.post(f"{URL}/liana-automation/test").json()["status"] == "connected"

    # 3. Channels: list, create, choose.
    assert {"id": "demo-1", "name": "Website"} in api.get(f"{URL}/liana-automation/channels").json()
    made = api.post(f"{URL}/liana-automation/channels", json={"name": "Survey tool (test)"})
    assert made.status_code == 201
    channel = made.json()
    chosen = api.patch(
        f"{URL}/liana-automation",
        json={"channel_id": channel["id"], "channel_name": channel["name"]},
    ).json()
    assert (chosen["channel_id"], chosen["channel_name"]) == (channel["id"], "Survey tool (test)")

    # 4. What to send.
    toggled = api.patch(f"{URL}/liana-automation", json={"settings": {"themes": True}}).json()
    assert toggled["settings"] == {"answers": True, "contact_requests": True, "themes": True}

    # 5. Test event, then the sync log and the counts.
    sent = api.post(f"{URL}/liana-automation/test-event", json={})
    assert sent.status_code == 201
    assert sent.json()["status"] == "sent" and sent.json()["contact"] == "su…@example.com"
    log = api.get(f"{URL}/liana-automation/events").json()
    assert log[0]["id"] == sent.json()["id"]
    assert api.get(URL).json()["events"] == {"sent": 1}

    # Saving again without a secret keeps the saved one; the connection must be tested again.
    again = api.put(f"{URL}/liana-automation", json={"host": "demo", "client_id": "demo-client"})
    assert again.json()["status"] == "disconnected"
    assert again.json()["channel_id"] == channel["id"]
    assert api.post(f"{URL}/liana-automation/test").json()["status"] == "connected"

    # Disconnect keeps the log.
    assert api.delete(f"{URL}/liana-automation").status_code == 204
    assert api.get(URL).json()["liana_automation"] is None
    assert len(api.get(f"{URL}/liana-automation/events").json()) == 1


def test_wrong_credentials_show_as_an_error(api):
    api.put(f"{URL}/liana-automation", json={**DEMO, "client_secret": "wrong-secret"})
    tested = api.post(f"{URL}/liana-automation/test").json()
    assert tested["status"] == "error"
    assert "Wrong client ID or secret" in tested["last_error"]
    assert api.get(f"{URL}/liana-automation/channels").status_code == 502


def test_failed_event_can_be_retried(api):
    api.put(f"{URL}/liana-automation", json=DEMO)
    api.patch(f"{URL}/liana-automation", json={"channel_id": "demo-1"})
    failed = api.post(f"{URL}/liana-automation/test-event", json={"email": "fail@example.com"})
    assert failed.json()["status"] == "failed" and "503" in failed.json()["last_error"]
    assert [e["id"] for e in api.get(f"{URL}/liana-automation/events?status=failed").json()] == [
        failed.json()["id"]
    ]

    class Healthy:
        def import_events(self, body):
            assert body["no_duplicates"] is True
            assert body["data"][0]["identity"] == {"email": "fail@example.com"}

    app.dependency_overrides[client_factory] = lambda: lambda *args: Healthy()
    retried = api.post(f"{URL}/events/{failed.json()['id']}/retry").json()
    assert (retried["status"], retried["attempts"], retried["last_error"]) == ("sent", 2, None)
    assert api.post(f"{URL}/events/{failed.json()['id']}/retry").status_code == 409
    assert api.post(f"{URL}/events/{uuid4()}/retry").status_code == 404


def test_a_double_click_on_retry_sends_once(api):
    api.put(f"{URL}/liana-automation", json=DEMO)
    api.patch(f"{URL}/liana-automation", json={"channel_id": "demo-1"})
    failed = api.post(f"{URL}/liana-automation/test-event", json={"email": "fail@example.com"})
    event_id = UUID(failed.json()["id"])
    with tenant_connection(DEMO_TENANT) as conn:
        conn.row_factory = dict_row
        assert repo.claim_event(conn, event_id)["status"] == "pending"  # the first click
    second = api.post(f"{URL}/events/{event_id}/retry")
    assert (
        second.status_code == 409 and second.json()["detail"] == "This event is already being sent."
    )


def _failed_event(api) -> str:
    api.put(f"{URL}/liana-automation", json=DEMO)
    api.patch(f"{URL}/liana-automation", json={"channel_id": "demo-1"})
    failed = api.post(f"{URL}/liana-automation/test-event", json={"email": "fail@example.com"})
    assert failed.json()["status"] == "failed"
    return failed.json()["id"]


def _status(api, event_id) -> str:
    return next(e for e in api.get(f"{URL}/liana-automation/events").json() if e["id"] == event_id)[
        "status"
    ]


def test_a_refused_retry_leaves_the_event_failed_and_retryable(api):
    event_id = _failed_event(api)
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("update integrations set channel_id = null")
    assert api.post(f"{URL}/events/{event_id}/retry").status_code == 409
    assert _status(api, event_id) == "failed"

    api.patch(f"{URL}/liana-automation", json={"channel_id": "demo-1"})

    class Healthy:
        def import_events(self, body):
            pass

    app.dependency_overrides[client_factory] = lambda: lambda *args: Healthy()
    assert api.post(f"{URL}/events/{event_id}/retry").json()["status"] == "sent"


def test_a_retry_after_disconnecting_leaves_the_event_failed(api):
    event_id = _failed_event(api)
    api.delete(f"{URL}/liana-automation")
    assert api.post(f"{URL}/events/{event_id}/retry").status_code == 404
    assert _status(api, event_id) == "failed"


def test_an_unexpected_error_puts_the_event_back_to_failed(api):
    event_id = _failed_event(api)

    class Broken:
        def import_events(self, body):
            raise KeyError("id")

    app.dependency_overrides[client_factory] = lambda: lambda *args: Broken()
    with pytest.raises(KeyError):
        api.post(f"{URL}/events/{event_id}/retry")
    [event] = [e for e in api.get(f"{URL}/liana-automation/events").json() if e["id"] == event_id]
    assert (event["status"], event["last_error"]) == ("failed", routes.UNEXPECTED)
    with pytest.raises(KeyError):
        api.post(f"{URL}/liana-automation/test-event", json={})
    assert {e["status"] for e in api.get(f"{URL}/liana-automation/events").json()} == {"failed"}


def test_a_refused_test_event_leaves_nothing_in_the_log(api, monkeypatch):
    api.put(f"{URL}/liana-automation", json=DEMO)
    api.patch(f"{URL}/liana-automation", json={"channel_id": "demo-1"})
    monkeypatch.setattr(routes, "demo_allowed", lambda: False)
    assert api.post(f"{URL}/liana-automation/test-event", json={}).status_code == 409
    assert api.get(f"{URL}/liana-automation/events").json() == []


def test_a_demo_connection_sends_nothing_outside_dev_mode(api, monkeypatch):
    api.put(f"{URL}/liana-automation", json=DEMO)
    monkeypatch.setattr(routes, "demo_allowed", lambda: False)
    tested = api.post(f"{URL}/liana-automation/test")
    assert (
        tested.status_code == 409 and "only works in local development" in tested.json()["detail"]
    )
    assert api.get(URL).json()["liana_automation"]["status"] == "error"


def test_secrets_are_not_saved_with_the_default_key_outside_dev(api, monkeypatch):
    monkeypatch.setattr(
        routes,
        "get_settings",
        lambda: Settings(auth_mode="oidc", integration_secret_key=secrets.DEV_KEY),
    )
    saved = api.put(
        f"{URL}/liana-automation",
        json={"host": "rest.automation.lianacloud.com", "client_id": "x", "client_secret": "y"},
    )
    assert saved.status_code == 500 and "INTEGRATION_SECRET_KEY" in saved.json()["detail"]


def test_a_wrong_host_marks_the_connection_broken(api):
    api.put(f"{URL}/liana-automation", json=DEMO)
    api.patch(f"{URL}/liana-automation", json={"channel_id": "demo-1"})

    class WrongHost:
        def import_events(self, body):
            raise ConfigError("Not found (404): check the host.")

    app.dependency_overrides[client_factory] = lambda: lambda *args: WrongHost()
    assert api.post(f"{URL}/liana-automation/test-event", json={}).json()["status"] == "failed"
    status = api.get(URL).json()["liana_automation"]
    assert (status["status"], status["last_error"]) == ("error", "Not found (404): check the host.")


@pytest.mark.parametrize(
    "body",
    [
        {"host": "evil.example.com", "client_id": "x", "client_secret": "y"},
        {"host": "demo", "client_id": "x"},  # no secret saved yet
    ],
)
def test_bad_credentials_input_is_refused(api, body):
    assert api.put(f"{URL}/liana-automation", json=body).status_code == 422


def test_test_events_only_go_to_example_contacts(api):
    api.put(f"{URL}/liana-automation", json=DEMO)
    res = api.post(f"{URL}/liana-automation/test-event", json={"email": "anna@gmail.com"})
    assert res.status_code == 422
    no_channel = api.post(f"{URL}/liana-automation/test-event", json={})
    assert no_channel.status_code == 409


def test_nothing_without_a_connection(api):
    assert api.post(f"{URL}/liana-automation/test").status_code == 404
    assert api.delete(f"{URL}/liana-automation").status_code == 404


def test_answers_not_sent_on_purpose_cannot_be_retried(api):
    with tenant_connection(DEMO_TENANT) as conn:
        event_id = conn.execute(
            """insert into integration_events (tenant_id, verb, payload, test, status, last_error)
               values (%s, 'survey_answered', '{}', true, 'skipped',
                       'Not sent: anonymous answer.') returning id""",
            (DEMO_TENANT,),
        ).fetchone()[0]
    r = api.post(f"{URL}/events/{event_id}/retry")
    assert r.status_code == 409 and "not sent on purpose" in r.json()["detail"]
    skipped = api.get(f"{URL}/liana-automation/events", params={"status": "skipped"}).json()
    assert [e["status"] for e in skipped] == ["skipped"]
    assert api.get(URL).json()["events"] == {"skipped": 1}


class Directory:
    """A fake LianaMailer for Retry: contact.<id>@example.com, 999 is unknown."""

    def email_for(self, contact_id):
        from liana_connector.ports.contact_directory import ContactNotFound

        if contact_id == "999":
            raise ContactNotFound(contact_id)
        return f"contact.{contact_id}@example.com"


def _waiting_answer(contact_id):
    """A survey_answered row that failed before its address could be looked up."""
    payload = {
        "identity": {"lianamailer_id": contact_id},
        "events": [{"verb": "survey_answered", "items": {"survey_id": "s1", "score": "9"}}],
    }
    with tenant_connection(DEMO_TENANT) as conn:
        return conn.execute(
            """insert into integration_events (tenant_id, verb, payload, test, status, last_error)
               values (%s, 'survey_answered', %s, true, 'failed', 'LianaMailer is not set up')
               returning id""",
            (DEMO_TENANT, Jsonb(payload)),
        ).fetchone()[0]


def test_retry_looks_the_contacts_address_up_before_sending(api):
    api.put(f"{URL}/liana-automation", json=DEMO)
    api.patch(f"{URL}/liana-automation", json={"channel_id": "demo-1"})
    app.dependency_overrides[routes.contact_directory] = Directory
    sent = api.post(f"{URL}/events/{_waiting_answer('4084399')}/retry").json()
    assert sent["status"] == "sent"
    # Sent with the address; the sync log keeps the contact id and a shortened address.
    assert sent["payload"]["identity"] == {"lianamailer_id": "4084399"}
    assert "contact.4084399@example.com" not in str(sent)
    assert sent["contact"] == "co…@example.com"
    assert sent["liana_response"].startswith("HTTP 200 ")

    unknown = api.post(f"{URL}/events/{_waiting_answer('999')}/retry").json()
    assert (unknown["status"], unknown["last_error"]) == (
        "skipped",
        "Not sent: contact not found in LianaMailer (r=999).",
    )


def test_the_status_says_whether_lianamailer_is_set_up(api):
    assert api.get(URL).json()["lianamailer_set_up"] is False
    app.dependency_overrides[routes.contact_directory] = Directory
    assert api.get(URL).json()["lianamailer_set_up"] is True
