"""LianaClient against a fake HTTP transport: tokens, and how each answer is classified."""

import json
from datetime import UTC, datetime

import httpx
import pytest

from liana_connector.automation import domain, secrets
from liana_connector.automation.client import (
    AuthError,
    ConfigError,
    DemoLianaClient,
    LianaClient,
    PermanentError,
    TemporaryError,
    build_client,
    token_url_for,
)


class FakeLiana:
    """Answers the token URL and the API; `answers` are status codes for API calls in order."""

    def __init__(self, answers=(), body=None, token_status=200, token_body=None):
        self.answers = list(answers)
        self.body = body if body is not None else {"ok": True}
        self.token_status = token_status
        self.token_body = token_body
        self.tokens = 0
        self.calls = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "tokens.lianacloud.com":
            self.tokens += 1
            form = dict(x.split("=") for x in request.content.decode().split("&"))
            assert form["grant_type"] == "client_credentials" and form["scope"] == "automation-api"
            if self.token_body is not None:
                return httpx.Response(200, text=self.token_body)
            return httpx.Response(
                self.token_status, json={"access_token": f"t{self.tokens}", "expires_in": 900}
            )
        self.calls.append((request.url.path, request.headers["Authorization"], request.content))
        status = self.answers.pop(0) if self.answers else 200
        if status == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        if status == "no connection":
            raise httpx.ConnectError("getaddrinfo failed", request=request)
        if status == "not json":
            return httpx.Response(200, text="<html>maintenance</html>")
        return httpx.Response(status, json=self.body if status == 200 else {"error": "x"})


def client(fake, clock=lambda: 0.0):
    http = httpx.Client(transport=httpx.MockTransport(fake))
    return LianaClient("rest.automation.lianacloud.com", "id", "secret", http=http, clock=clock)


def test_token_is_reused_until_a_minute_before_it_expires():
    now = [0.0]
    fake = FakeLiana()
    c = client(fake, clock=lambda: now[0])
    c.ping()
    c.ping()
    assert fake.tokens == 1
    now[0] = 900 - 59
    c.ping()
    assert fake.tokens == 2
    path, auth, body = fake.calls[0]
    assert path == "/api/v1/pingpong" and auth == "Bearer t1"
    assert json.loads(body) == {"ping": "pong"}


def test_staging_hosts_use_the_staging_token_service():
    assert token_url_for("rest.automation.lianacloud.com") == "https://tokens.lianacloud.com/token"
    assert token_url_for("rest.automation.stg.lianacloud.com") == (
        "https://tokens.stg.lianacloud.com/token"
    )
    assert token_url_for("stgfoo.lianacloud.com") == "https://tokens.lianacloud.com/token"


def test_a_401_gets_a_new_token_and_is_retried_once():
    fake = FakeLiana(answers=[401, 200])
    client(fake).ping()
    assert fake.tokens == 2 and len(fake.calls) == 2
    with pytest.raises(AuthError):
        client(FakeLiana(answers=[401, 401])).ping()


@pytest.mark.parametrize(
    "answer, error",
    [
        (400, PermanentError),
        (404, ConfigError),
        (500, TemporaryError),
        (503, TemporaryError),
        ("timeout", TemporaryError),
        # A DNS blip or outage must not mark a correct connection as broken.
        ("no connection", TemporaryError),
        ("not json", PermanentError),
    ],
)
def test_answers_are_classified(answer, error):
    with pytest.raises(error):
        client(FakeLiana(answers=[answer])).import_events({"channel": "1", "data": []})


def test_an_unexpected_token_answer_is_temporary():
    for body in ("<html>", "{}", "[1]"):
        with pytest.raises(TemporaryError):
            client(FakeLiana(token_body=body)).ping()


def test_the_demo_host_only_works_when_allowed():
    assert isinstance(
        build_client("demo", "demo-client", "demo-secret", allow_demo=True), DemoLianaClient
    )
    with pytest.raises(ConfigError):
        build_client("demo", "demo-client", "demo-secret", allow_demo=False)
    real = build_client("rest.automation.lianacloud.com", "id", "s", allow_demo=False)
    assert isinstance(real, LianaClient)


def test_wrong_credentials_at_the_token_service():
    with pytest.raises(AuthError):
        client(FakeLiana(token_status=401)).ping()
    with pytest.raises(TemporaryError):
        client(FakeLiana(token_status=502)).ping()


@pytest.mark.parametrize(
    "body",
    [
        [{"id": 7, "name": "Survey tool (test)"}],
        {"items": [{"id": "7", "name": "Survey tool (test)"}, {"name": "no id"}]},
        {"channels": [{"channel_id": 7, "title": "Survey tool (test)"}]},
    ],
)
def test_channel_lists_in_any_of_the_usual_shapes(body):
    assert client(FakeLiana(body=body)).channels() == [{"id": "7", "name": "Survey tool (test)"}]


def test_demo_client():
    demo = DemoLianaClient("demo-client", "demo-secret")
    demo.ping()
    made = demo.create_channel("Survey tool (test)")
    assert made in demo.channels()
    demo.import_events(domain.import_body(made["id"], [domain.test_event("a@example.com", NOW)]))
    with pytest.raises(PermanentError):
        demo.import_events(domain.import_body("42", []))
    with pytest.raises(TemporaryError):
        demo.import_events(
            domain.import_body(made["id"], [{"identity": {"email": "fail@example.com"}}])
        )
    with pytest.raises(AuthError):
        DemoLianaClient("demo-client", "wrong").ping()


NOW = datetime(2026, 11, 23, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "host, expected",
    [
        ("rest.automation.lianacloud.com", "rest.automation.lianacloud.com"),
        ("https://REST.automation.lianacloud.com/", "rest.automation.lianacloud.com"),
        ("demo", "demo"),
    ],
)
def test_allowed_hosts(host, expected):
    assert domain.clean_host(host, allow_demo=True) == expected


@pytest.mark.parametrize(
    "host",
    [
        "evil.example.com",
        "lianacloud.com.evil.com",
        "localhost",
        "10.0.0.1",
        "rest.automation.lianacloud.com/../x",
        "rest.automation.lianacloud.com:8080",
        "",
    ],
)
def test_other_hosts_are_refused(host):
    with pytest.raises(domain.InvalidInput):
        domain.clean_host(host, allow_demo=True)
    with pytest.raises(domain.InvalidInput):
        domain.clean_host("demo", allow_demo=False)


def test_rules():
    assert domain.secret_hint("abcdefgha91f") == "a91f"
    assert domain.secret_hint("short") == ""
    assert domain.merged_settings(
        {"answers": False, "x": True}, {"themes": True, "answers": "yes"}
    ) == {
        "answers": False,
        "contact_requests": True,
        "themes": True,
    }
    assert [domain.nps_group(s) for s in (0, 6, 7, 8, 9, 10)] == [
        "detractor",
        "detractor",
        "passive",
        "passive",
        "promoter",
        "promoter",
    ]
    assert domain.test_contact(None) == "survey-test-1@example.com"
    assert domain.test_contact(" Test-2@Example.com ") == "test-2@example.com"
    for bad in ("anna@gmail.com", "a@b@example.com", "example.com"):
        with pytest.raises(domain.InvalidInput):
            domain.test_contact(bad)
    assert domain.masked_email("survey-test-1@example.com") == "su…@example.com"
    event = domain.test_event("a@example.com", NOW)
    items = event["events"][0]["items"]
    assert event["identity"] == {"email": "a@example.com"}
    assert (items["score"], items["nps_group"]) == ("3", "detractor")
    assert items["test_sent_at"] == "2026-11-23T10:00:00+00:00"
    assert domain.import_body("7", [event]) == {
        "channel": "7",
        "no_duplicates": True,
        "data": [event],
    }


def test_secrets_round_trip_and_need_the_same_key():
    token = secrets.encrypt("my-secret", "key-1")
    assert b"my-secret" not in token
    assert secrets.decrypt(token, "key-1") == "my-secret"
    with pytest.raises(secrets.UnreadableSecret):
        secrets.decrypt(token, "key-2")


def test_the_default_or_a_short_key_is_refused_outside_dev():
    assert secrets.check_key(secrets.DEV_KEY, "dev") == secrets.DEV_KEY
    for weak in (secrets.DEV_KEY, "short", "x" * 31):
        with pytest.raises(secrets.WeakKey):
            secrets.check_key(weak, "oidc")
    strong = "k" * 32
    assert secrets.check_key(strong, "oidc") == strong


def test_the_api_refuses_to_start_with_the_default_key_outside_dev(monkeypatch):
    from fastapi.testclient import TestClient

    from liana_connector import api
    from liana_survey_shared.config import Settings

    monkeypatch.setattr(
        api,
        "get_settings",
        lambda: Settings(auth_mode="oidc", integration_secret_key=secrets.DEV_KEY),
    )
    with pytest.raises(secrets.WeakKey), TestClient(api.app):
        pass


# --- Sent only when Liana accepted the event -------------------------------------------


def test_an_accepted_import_returns_lianas_answer_for_the_sync_log():
    fake = FakeLiana(body={"succeed": True, "imported": 1})
    answer = client(fake).import_events({"channel": "1", "data": []})
    assert answer == 'HTTP 200 {"succeed":true,"imported":1}'


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ({"succeed": False, "message": "unknown identity"}, "unknown identity"),
        ({"success": False}, "success is false"),
        ({"errors": [{"index": 0, "message": "bad email"}]}, "bad email"),
        ({"imported": 0, "rejected": 1}, "rejected: 1"),
        ({"results": [{"ok": True}, {"error": "no such contact"}]}, "no such contact"),
    ],
)
def test_a_200_whose_body_refuses_the_event_is_a_permanent_error(body, reason):
    with pytest.raises(PermanentError, match=reason) as refused:
        client(FakeLiana(body=body)).import_events({"channel": "1", "data": []})
    assert refused.value.response.startswith("HTTP 200 ")


def test_an_import_answer_that_says_nothing_wrong_is_accepted():
    for body in ({}, {"ok": True}, {"imported": 2, "failed": 0, "errors": []}, [1, 2]):
        assert domain.import_problem(body) is None


def test_a_refused_call_keeps_lianas_answer():
    with pytest.raises(PermanentError) as refused:
        client(FakeLiana(answers=[400])).import_events({"channel": "1", "data": []})
    assert refused.value.response == 'HTTP 400 {"error":"x"}'


def test_email_addresses_in_lianas_answer_are_hidden_before_it_is_kept_or_logged():
    body = {"succeed": True, "imported": [{"email": "test.anna@example.com", "id": 7}]}
    answer = client(FakeLiana(body=body)).import_events({"channel": "1", "data": []})
    assert "test.anna@example.com" not in answer
    assert '"email":"[email]"' in answer


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (200, {"succeed": False, "message": "Invalid email anna@example.com"}),
        (200, {"errors": [{"identity": "test.mikko@example.com", "error": "unknown"}]}),
        (400, {"error": "No contact anna@example.com"}),
        (409, {"error": "Conflict for anna@example.com"}),
    ],
)
def test_an_address_in_lianas_error_never_reaches_the_sync_log(status, body):
    # From review: last_error is kept in the sync log, so Liana's own message is
    # scrubbed too, not only the stored answer.
    def answer(request):
        if request.url.host == "tokens.lianacloud.com":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 900})
        return httpx.Response(status, json=body)

    http = httpx.Client(transport=httpx.MockTransport(answer))
    c = LianaClient("rest.automation.lianacloud.com", "id", "secret", http=http)
    with pytest.raises(PermanentError) as refused:
        c.import_events({"channel": "1", "data": []})
    assert "@example.com" not in str(refused.value)
    assert "@example.com" not in refused.value.response
    assert "[email]" in refused.value.response
