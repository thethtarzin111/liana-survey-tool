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
    token_url_for,
)


class FakeLiana:
    """Answers the token URL and the API; `answers` are status codes for API calls in order."""

    def __init__(self, answers=(), body=None, token_status=200):
        self.answers = list(answers)
        self.body = body if body is not None else {"ok": True}
        self.token_status = token_status
        self.tokens = 0
        self.calls = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "tokens.lianacloud.com":
            self.tokens += 1
            form = dict(x.split("=") for x in request.content.decode().split("&"))
            assert form["grant_type"] == "client_credentials" and form["scope"] == "automation-api"
            return httpx.Response(
                self.token_status, json={"access_token": f"t{self.tokens}", "expires_in": 900}
            )
        self.calls.append((request.url.path, request.headers["Authorization"], request.content))
        status = self.answers.pop(0) if self.answers else 200
        if status == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
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
    ],
)
def test_answers_are_classified(answer, error):
    with pytest.raises(error):
        client(FakeLiana(answers=[answer])).import_events({"channel": "1", "data": []})


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
