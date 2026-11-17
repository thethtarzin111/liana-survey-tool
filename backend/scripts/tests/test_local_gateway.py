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
    monkeypatch.setattr(handlers, "handle_answer", lambda body: saved.append(body) or True)
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
