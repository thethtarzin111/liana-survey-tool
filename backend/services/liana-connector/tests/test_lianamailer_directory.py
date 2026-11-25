"""The LianaMailer contact directory: HMAC signing as in the API docs, and how each
answer of POST /api/v1/getRecipient is read."""

import json
from datetime import UTC, datetime

import httpx
import pytest

from liana_connector.adapters.lianamailer.directory import (
    DemoDirectory,
    LianaMailerDirectory,
    NotSetUp,
    signature,
    signed_headers,
)
from liana_connector.factory import build_contact_directory
from liana_connector.ports.contact_directory import (
    ContactNotFound,
    DirectoryNotSetUp,
    DirectoryUnavailable,
)
from liana_survey_shared.config import Settings

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


def test_the_signature_matches_the_worked_examples_in_the_api_docs():
    # https://rest.lianamailer.com/docs/ "Using HMAC signature", V1 and V3 examples.
    secret = "0123456789abcdef0123456789abcdef"
    headers = signed_headers(
        "EUR",
        "123",
        secret,
        "POST",
        '["hello"]',
        "/api/v1/echoMessage",
        "2020-01-15T12:00:00+03:00",
    )
    assert headers["Content-MD5"] == "1f0bf5038e61951a95c4a2a9db7c400a"
    assert headers["Authorization"] == (
        "EUR 123:89b60df150aad61e42fef7d6a43883c83e642aef2f7f2338b971c681f9992c26"
    )
    assert (
        signature(
            secret,
            "GET",
            "d41d8cd98f00b204e9800998ecf8427e",
            "2020-01-15T12:00:00+03:00",
            "",
            "/api/v3/events?type=mailopen&at_start=2020-01-10T12:00:00&at_end=2020-01-10T15:00:00",
        )
        == "22404d156bd828b157c3e6e11f5b83943b00bc7b0029eceab304dae227ef7f03"
    )


def directory(answer):
    """A directory whose API answers with `answer(request)`; requests are kept."""
    seen = []

    def handle(request):
        seen.append(request)
        return answer(request)

    http = httpx.Client(transport=httpx.MockTransport(handle))
    return LianaMailerDirectory(
        "rest.lianamailer.com", "123", "s3cret", http=http, now=lambda: NOW
    ), seen


def test_the_email_address_comes_from_a_signed_get_recipient_call():
    found = {
        "succeed": True,
        "result": {"recipient": {"id": 4084400, "email": "Test.Mikko@Example.com"}},
    }
    d, seen = directory(lambda request: httpx.Response(200, json=found))
    assert d.email_for("4084400") == "test.mikko@example.com"
    [request] = seen
    assert str(request.url) == "https://rest.lianamailer.com/api/v1/getRecipient"
    body = request.content.decode()
    assert json.loads(body) == [
        4084400,
        {"include_consents": False, "include_list_memberships": False, "include_properties": False},
    ]
    # The signed body is exactly the body sent.
    expected = signed_headers(
        "EUR", "123", "s3cret", "POST", body, "/api/v1/getRecipient", NOW.isoformat()
    )
    for name in ("Content-MD5", "Date", "Authorization", "Content-Type"):
        assert request.headers[name] == expected[name]


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(404, json={"succeed": False}),
        httpx.Response(200, json={"succeed": False, "message": "Recipient not found"}),
        httpx.Response(200, json={"succeed": True, "result": {"recipient": {"id": 1}}}),
        httpx.Response(200, json={"succeed": True, "result": None}),
    ],
)
def test_an_unknown_contact_is_not_found(answer):
    d, _ = directory(lambda request: answer)
    with pytest.raises(ContactNotFound):
        d.email_for("999")


def test_a_contact_id_that_is_not_a_number_is_not_looked_up():
    d, seen = directory(lambda request: httpx.Response(500))
    with pytest.raises(ContactNotFound):
        d.email_for("contact-42")
    assert seen == []


def test_refused_credentials_say_what_to_set():
    d, _ = directory(lambda request: httpx.Response(401, json={"succeed": False}))
    with pytest.raises(DirectoryNotSetUp, match="LIANAMAILER_API_USER"):
        d.email_for("4084400")


@pytest.mark.parametrize("status", [429, 500, 503])
def test_a_busy_or_broken_lianamailer_is_temporary(status):
    d, _ = directory(lambda request: httpx.Response(status))
    with pytest.raises(DirectoryUnavailable):
        d.email_for("4084400")


def test_no_connection_is_temporary():
    def down(request):
        raise httpx.ConnectError("no route", request=request)

    d, _ = directory(down)
    with pytest.raises(DirectoryUnavailable):
        d.email_for("4084400")


def test_the_factory_picks_the_directory_from_the_settings():
    assert isinstance(build_contact_directory(Settings()), NotSetUp)
    real = build_contact_directory(
        Settings(
            lianamailer_api_host="rest.lianamailer.com",
            lianamailer_api_user="123",
            lianamailer_api_secret="s",
        )
    )
    assert isinstance(real, LianaMailerDirectory) and real.base == "https://rest.lianamailer.com"
    assert isinstance(build_contact_directory(Settings(lianamailer_api_host="demo")), DemoDirectory)
    # The fake never outside local development.
    assert isinstance(
        build_contact_directory(Settings(lianamailer_api_host="demo", auth_mode="oidc")), NotSetUp
    )


def test_the_demo_directory_only_makes_example_addresses():
    demo = DemoDirectory()
    assert demo.email_for("4084399") == "contact.4084399@example.com"
    assert "fail" in demo.email_for("4084666")
    with pytest.raises(ContactNotFound):
        demo.email_for("999")
    with pytest.raises(DirectoryNotSetUp, match="not set up"):
        NotSetUp().email_for("4084399")


def test_the_demo_lianamailer_is_refused_outside_local_development():
    for mode in ("oidc", "production", ""):
        directory = build_contact_directory(Settings(lianamailer_api_host="demo", auth_mode=mode))
        assert isinstance(directory, NotSetUp)
        with pytest.raises(DirectoryNotSetUp, match="only works in local development"):
            directory.email_for("4084399")
