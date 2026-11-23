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


def test_without_rabbitmq_a_contact_request_goes_straight_to_the_mock_adapter(monkeypatch):
    import asyncio
    from uuid import uuid4

    import survey_worker.handlers as handlers
    from liana_survey_shared.messages import AnswerSubmitted, ContactRequested

    settings = get_settings()
    request = ContactRequested(
        tenant_id=settings.dev_tenant_id,
        survey_id=settings.dev_tenant_id,
        contact_request_id=uuid4(),
        contact_ref="member-1042",
    )
    monkeypatch.setattr(
        handlers, "record_answer", lambda body: handlers.Recorded(True, None, request)
    )
    events = local_gateway.DirectLianaEvents()
    stored = []
    events.record = lambda event, status, attempts: stored.append((status, attempts))
    message = AnswerSubmitted(
        tenant_id=settings.dev_tenant_id,
        survey_id=settings.dev_tenant_id,
        link_token_hash="key",
        answers=[],
        contact_ref="member-1042",
    )
    asyncio.run(local_gateway.DirectAnswerQueue(events).publish(message))
    assert events.contacts.sent == [request]
    assert stored == [("sent", 1)]
