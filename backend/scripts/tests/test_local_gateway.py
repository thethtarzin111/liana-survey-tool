from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from backend.scripts import local_gateway
from liana_survey_shared.config import get_settings


def test_me_uses_demo_identity_even_with_spoofed_headers():
    with TestClient(local_gateway.app) as client:
        response = client.get("/api/v1/me", headers={"X-User-Id": "spoofed"})
    assert response.status_code == 200
    assert response.json()["user_id"] == str(get_settings().dev_user_id)


def test_routing_preserves_request_and_replaces_identity(monkeypatch):
    async def capture(scope, receive, send):
        headers = dict(scope["headers"])
        await JSONResponse(
            {
                "path": scope["path"],
                "method": scope["method"],
                "query": scope["query_string"].decode(),
                "user": headers.get(b"x-user-id", b"").decode(),
            }
        )(scope, receive, send)

    monkeypatch.setattr(local_gateway, "surveys", capture)
    monkeypatch.setattr(local_gateway, "respondent", capture)
    with TestClient(local_gateway.app) as client:
        admin = client.patch("/api/v1/surveys/123?test=1", headers={"X-User-Id": "fake"})
        public = client.get("/r/token", headers={"X-User-Id": "fake"})
        missing = client.get("/api/v1/surveys-other")
    assert admin.json() == {
        "path": "/api/v1/surveys/123",
        "method": "PATCH",
        "query": "test=1",
        "user": str(get_settings().dev_user_id),
    }
    assert public.json()["user"] == ""
    assert missing.status_code == 404


LUT_STUDENTS = "00000000-0000-4000-8000-000000000002"


def test_the_demo_organizations_are_listed_with_the_default_one_current():
    with TestClient(local_gateway.app) as client:
        organizations = client.get("/api/v1/me/organizations").json()
    assert [o["tenant_name"] for o in organizations] == [
        get_settings().dev_tenant_name,
        "LUT Students",
    ]
    assert [o["current"] for o in organizations] == [True, False]


def test_switching_organization_changes_the_user_for_every_admin_request(monkeypatch):
    async def capture(scope, receive, send):
        headers = dict(scope["headers"])
        await JSONResponse({"tenant": headers.get(b"x-tenant-id", b"").decode()})(
            scope, receive, send
        )

    monkeypatch.setattr(local_gateway, "surveys", capture)
    monkeypatch.setattr(local_gateway, "respondent", capture)
    with TestClient(local_gateway.app) as client:
        switched = client.put("/api/v1/me/organizations", json={"tenant_id": LUT_STUDENTS})
        assert switched.status_code == 200
        assert switched.json()["name"] == "Mikko Korhonen"
        assert "httponly" in switched.headers["set-cookie"].lower()
        assert client.get("/api/v1/me").json()["tenant_id"] == LUT_STUDENTS
        assert client.get("/api/v1/surveys").json() == {"tenant": LUT_STUDENTS}
        # Identity headers from the browser are still replaced, and links stay public.
        spoofed = client.get("/api/v1/surveys", headers={"X-Tenant-Id": "other"})
        assert spoofed.json() == {"tenant": LUT_STUDENTS}
        assert client.get("/r/token").json() == {"tenant": ""}
        current = [o["current"] for o in client.get("/api/v1/me/organizations").json()]
        assert current == [False, True]


def test_an_unknown_organization_is_refused_and_the_default_stays():
    with TestClient(local_gateway.app) as client:
        unknown = client.put("/api/v1/me/organizations", json={"tenant_id": "someone-else"})
        broken = client.put("/api/v1/me/organizations", content=b"not json")
        deleted = client.delete("/api/v1/me/organizations")
        me = client.get("/api/v1/me").json()
    assert unknown.status_code == 422
    assert broken.status_code == 422
    assert deleted.status_code == 405
    assert me["tenant_id"] == str(get_settings().dev_tenant_id)


def test_a_forged_cookie_for_an_unknown_organization_gets_the_default_user():
    with TestClient(local_gateway.app, cookies={"demo_org": "someone-else"}) as client:
        me = client.get("/api/v1/me").json()
    assert me["tenant_id"] == str(get_settings().dev_tenant_id)


MEMBERS = "00000000-0000-4000-8000-000000000001"
LOGINS = f"liana={MEMBERS}, lutstudents={LUT_STUDENTS}"


def test_on_the_demo_server_each_login_gets_its_own_organization(monkeypatch):
    async def capture(scope, receive, send):
        headers = dict(scope["headers"])
        await JSONResponse(
            {
                "tenant": headers.get(b"x-tenant-id", b"").decode(),
                "login": headers.get(b"x-demo-login", b"").decode(),
            }
        )(scope, receive, send)

    monkeypatch.setenv("DEMO_LOGINS", LOGINS)
    monkeypatch.setattr(local_gateway, "surveys", capture)
    monkeypatch.setattr(local_gateway, "respondent", capture)
    with TestClient(local_gateway.app) as client:
        students = {"X-Demo-Login": "lutstudents"}
        assert client.get("/api/v1/me", headers=students).json()["name"] == "Mikko Korhonen"
        assert client.get("/api/v1/surveys", headers=students).json() == {
            "tenant": LUT_STUDENTS,
            "login": "",
        }
        members = client.get("/api/v1/surveys", headers={"X-Demo-Login": "liana"})
        assert members.json()["tenant"] == MEMBERS
        # The login decides, not the cookie from the user menu.
        client.cookies.set("demo_org", MEMBERS)
        assert client.get("/api/v1/me", headers=students).json()["tenant_id"] == LUT_STUDENTS
        # Survey links stay public, without a login.
        assert client.get("/r/token").json() == {"tenant": "", "login": ""}


def test_a_demo_login_cannot_switch_organization(monkeypatch):
    monkeypatch.setenv("DEMO_LOGINS", LOGINS)
    with TestClient(local_gateway.app, headers={"X-Demo-Login": "liana"}) as client:
        organizations = client.get("/api/v1/me/organizations").json()
        switched = client.put("/api/v1/me/organizations", json={"tenant_id": LUT_STUDENTS})
        me = client.get("/api/v1/me").json()
    # One organisation, so the user menu shows no switcher.
    assert [o["tenant_id"] for o in organizations] == [MEMBERS]
    assert switched.status_code == 403
    assert "set-cookie" not in switched.headers
    assert me["tenant_id"] == MEMBERS


def test_without_a_known_demo_login_the_api_refuses(monkeypatch):
    monkeypatch.setenv("DEMO_LOGINS", LOGINS)
    with TestClient(local_gateway.app) as client:
        missing = client.get("/api/v1/surveys")
        unknown = client.get("/api/v1/me", headers={"X-Demo-Login": "someone"})
        health = client.get("/health")
    assert missing.status_code == 401
    assert unknown.status_code == 401
    assert health.status_code == 200


def test_a_demo_login_for_an_unknown_organization_is_a_setup_error(monkeypatch):
    import pytest

    monkeypatch.setenv("DEMO_LOGINS", "liana=00000000-0000-4000-8000-000000000999")
    with pytest.raises(RuntimeError, match="DEMO_LOGINS"):
        local_gateway.demo_logins()


def test_gateway_rejects_non_dev_auth(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_mode", "production")
    with TestClient(local_gateway.app) as client:
        assert client.get("/api/v1/me").status_code == 403


def test_without_rabbitmq_answers_go_straight_to_the_worker_code(monkeypatch):
    import asyncio

    import survey_worker.handlers as handlers
    from liana_survey_shared.messages import AnswerSubmitted

    saved = []
    monkeypatch.setattr(
        handlers, "record_answer", lambda body: saved.append(body) or handlers.Recorded(True)
    )
    message = AnswerSubmitted(
        tenant_id=get_settings().dev_tenant_id,
        survey_id=get_settings().dev_tenant_id,
        link_token_hash="key",
        answers=[],
    )
    asyncio.run(local_gateway.DirectAnswerQueue().publish(message))
    assert saved == [message.model_dump_json().encode()]
    # The respondent app in this process uses it (LOCAL_QUEUE_WORKERS is not 1 in tests).
    assert isinstance(local_gateway.respondent.state.answer_queue, local_gateway.DirectAnswerQueue)


def test_without_rabbitmq_a_due_email_goes_straight_to_the_mock_mail(monkeypatch):
    import asyncio

    import survey_worker.handlers as handlers
    from liana_survey_shared.messages import AnswerSubmitted, NewResponsesDigest

    settings = get_settings()
    digest = NewResponsesDigest(
        tenant_id=settings.dev_tenant_id,
        survey_id=settings.dev_tenant_id,
        survey_title="Poll",
        new_responses=1,
        total_responses=1,
        results_url="http://localhost:4200/results",
        recipient_email=settings.dev_user_email,
        recipient_name=settings.dev_user_name,
    )
    monkeypatch.setattr(handlers, "record_answer", lambda body: handlers.Recorded(True, digest))
    events = local_gateway.DirectLianaEvents()
    message = AnswerSubmitted(
        tenant_id=settings.dev_tenant_id,
        survey_id=settings.dev_tenant_id,
        link_token_hash="key",
        answers=[],
    )
    asyncio.run(local_gateway.DirectAnswerQueue(events).publish(message))
    assert [email.subject for email in events.mail.sent] == ["Poll: 1 new response"]


def test_without_rabbitmq_saved_answers_and_contact_requests_reach_the_connector(monkeypatch):
    import asyncio
    from uuid import uuid4

    import survey_worker.handlers as handlers
    from liana_connector.adapters.mock.adapter import MockContactEvents
    from liana_survey_shared.messages import AnswerRecorded, AnswerSubmitted, ContactRequested

    tenant = get_settings().dev_tenant_id
    recorded = AnswerRecorded(
        tenant_id=tenant,
        survey_id=uuid4(),
        response_id=uuid4(),
        survey_title="Poll",
        contact_ref="4084400",
    )
    request = ContactRequested(
        tenant_id=tenant, survey_id=uuid4(), contact_request_id=uuid4(), contact_ref="4084400"
    )
    monkeypatch.setattr(
        handlers, "record_answer", lambda body: handlers.Recorded(True, None, (recorded, request))
    )
    events = local_gateway.DirectLianaEvents()
    events.contacts = MockContactEvents()
    message = AnswerSubmitted(tenant_id=tenant, survey_id=uuid4(), link_token_hash="k", answers=[])
    asyncio.run(local_gateway.DirectAnswerQueue(events).publish(message))
    assert events.contacts.answers == [recorded]
    assert events.contacts.sent == [request]

    # A failed delivery (the sync log shows it) never fails the reader's answer.
    class Broken(MockContactEvents):
        def send_answer_recorded(self, event):
            raise RuntimeError("Liana is down")

    events.contacts = Broken()
    asyncio.run(local_gateway.DirectAnswerQueue(events).publish(message))
    assert events.contacts.sent == [request]
