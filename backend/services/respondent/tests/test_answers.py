"""The answer link (#42). Tests marked `db` need a migrated Postgres reached as
the app role; they delete the surveys they create. The queue is a fake."""

import os
import secrets
from urllib.parse import urlsplit
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from liana_survey_shared import links
from liana_survey_shared.config import get_settings
from liana_survey_shared.db import ping, tenant_connection
from respondent_service.domain import AnswerProblem, check_open, one_tap_answer
from respondent_service.main import app
from respondent_service.pages import page, thank_you
from respondent_service.routes import get_answer_queue

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")
needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)


# --- Rules and pages ------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "raw", "value"),
    [("nps", "0", 0), ("nps", " 10 ", 10), ("thumbs", "2", 2), ("rating", "1", 1)],
)
def test_answers_on_the_scale_are_accepted(kind, raw, value):
    assert one_tap_answer(kind, raw) == value


@pytest.mark.parametrize(
    ("kind", "raw", "status"),
    [
        ("nps", "11", 400),
        ("nps", "-1", 400),
        ("rating", "0", 400),
        ("thumbs", "3", 400),
        ("nps", "9.5", 400),
        ("nps", "nine", 400),
        ("nps", None, 400),
        ("nps", "", 400),
        ("single_choice", "1", 400),  # not a one-tap survey
        (None, "1", 400),  # no questions
    ],
)
def test_other_answers_are_refused(kind, raw, status):
    with pytest.raises(AnswerProblem) as problem:
        one_tap_answer(kind, raw)
    assert problem.value.status_code == status


def test_only_live_surveys_take_answers():
    check_open("live")
    with pytest.raises(AnswerProblem, match="closed") as closed:
        check_open("closed")
    assert closed.value.status_code == 410
    for status in ("draft", "scheduled"):
        with pytest.raises(AnswerProblem, match="not open yet"):
            check_open(status)


def test_pages_escape_survey_texts_and_ignore_odd_colours():
    html = thank_you("<script>alert(1)</script>", "red;}</style><script>", "#F0F9F6")
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html
    assert "red;}" not in html
    assert "#F0F9F6" in html
    assert "Your answer was saved." in thank_you("  ", None, None)
    assert "<title>Hi &amp; bye</title>" in page("Hi & bye", "x")


# --- The link, with a database ----------------------------------------------------


class FakeQueue:
    def __init__(self, fail: bool = False):
        self.messages = []
        self.fail = fail

    async def publish(self, message):
        if self.fail:
            raise ConnectionError("rabbitmq is down")
        self.messages.append(message)


@pytest.fixture
def queue():
    fake = FakeQueue()
    app.dependency_overrides[get_answer_queue] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def client(queue):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_survey():
    """A published survey for the demo tenant; deleted afterwards."""
    made: list[UUID] = []

    def create(status="live", kind="nps", survey_type="nps", thank_you_text="Thanks a lot!"):
        token = secrets.token_urlsafe(16)
        with tenant_connection(DEMO_TENANT) as conn:
            survey_id = conn.execute(
                """insert into surveys (tenant_id, title, type, status, thank_you, link_token)
                   values (%s, 'Answer test', %s, %s, %s, %s) returning id""",
                (DEMO_TENANT, survey_type, status, thank_you_text, token),
            ).fetchone()[0]
            main_id = conn.execute(
                """insert into questions (tenant_id, survey_id, position, kind, prompt)
                   values (%s, %s, 1, %s, 'Main?') returning id""",
                (DEMO_TENANT, survey_id, kind),
            ).fetchone()[0]
            conn.execute(
                "insert into survey_links (link_token, survey_id, tenant_id) values (%s, %s, %s)",
                (token, survey_id, DEMO_TENANT),
            )
        made.append(survey_id)
        return survey_id, main_id, token

    yield create
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("delete from surveys where id = any(%s)", (made,))


def link(token, reader="contact-42", answer=None):
    settings = get_settings()
    url = links.answer_link(settings.public_base_url, settings.link_signing_secret, token, reader)
    parts = urlsplit(url)
    return parts.path + "?" + parts.query + (f"&a={answer}" if answer is not None else "")


@pytest.mark.db
@needs_db
def test_a_tap_queues_the_answer_and_shows_the_thank_you_page(client, queue, make_survey):
    survey_id, main_id, token = make_survey()
    r = client.get(link(token, answer=9))
    assert r.status_code == 200
    assert "Thank you!" in r.text
    assert "Thanks a lot!" in r.text
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["referrer-policy"] == "no-referrer"

    [message] = queue.messages
    assert (message.tenant_id, message.survey_id) == (DEMO_TENANT, survey_id)
    assert [(a.question_id, a.number) for a in message.answers] == [(main_id, 9)]
    # Anonymous: a key to count the reader once, not the reader reference.
    secret = get_settings().link_signing_secret
    assert message.link_token_hash == links.response_key(secret, token, "contact-42")
    assert "contact-42" not in message.model_dump_json()
    assert message.contact_ref is None


@pytest.mark.db
@needs_db
def test_the_same_link_twice_gives_the_same_key(client, queue, make_survey):
    _, _, token = make_survey()
    client.get(link(token, answer=9))
    client.get(link(token, answer=3))
    client.get(link(token, reader="someone-else", answer=3))
    keys = [m.link_token_hash for m in queue.messages]
    # The worker saves the first answer for a key and ignores the rest (#23).
    assert keys[0] == keys[1] != keys[2]


@pytest.mark.db
@needs_db
@pytest.mark.parametrize(
    ("kind", "survey_type", "answer"), [("thumbs", "thumbs", 0), ("rating", "csat", 5)]
)
def test_thumbs_and_csat_taps(client, queue, make_survey, kind, survey_type, answer):
    _, _, token = make_survey(kind=kind, survey_type=survey_type)
    assert client.get(link(token, answer=answer)).status_code == 200
    assert queue.messages[0].answers[0].number == answer


@pytest.mark.db
@needs_db
def test_unknown_and_tampered_links_are_refused(client, queue, make_survey):
    _, _, token = make_survey()
    assert client.get(link("x" * 22, answer=9)).status_code == 404
    tampered = link(token, answer=9).replace("contact-42", "contact-43")
    r = client.get(tampered)
    assert r.status_code == 400
    assert "not complete or not valid" in r.text
    assert client.get(f"/r/{token}?a=9").status_code == 400  # no reader or signature
    assert queue.messages == []


@pytest.mark.db
@needs_db
@pytest.mark.parametrize(
    ("status", "code", "text"),
    [
        ("closed", 410, "This survey is closed"),
        ("draft", 403, "not open yet"),
        ("scheduled", 403, "not open yet"),
    ],
)
def test_surveys_that_are_not_live_show_a_clear_message(
    client, queue, make_survey, status, code, text
):
    _, _, token = make_survey(status=status)
    r = client.get(link(token, answer=9))
    assert r.status_code == code
    assert text in r.text
    assert queue.messages == []


@pytest.mark.db
@needs_db
def test_wrong_answers_are_refused_before_queueing(client, queue, make_survey):
    _, _, token = make_survey()
    assert client.get(link(token, answer=11)).status_code == 400
    r = client.get(link(token))
    assert (r.status_code, "Choose an answer" in r.text) == (400, True)
    assert queue.messages == []


@pytest.mark.db
@needs_db
def test_a_queue_outage_asks_the_reader_to_try_again(client, queue, make_survey):
    _, _, token = make_survey()
    queue.fail = True
    r = client.get(link(token, answer=9))
    assert r.status_code == 503
    assert "Please open the link again" in r.text


def test_the_queue_is_made_on_first_use_without_a_lifespan():
    # The local gateway runs this app without its lifespan.
    from types import SimpleNamespace

    from respondent_service.answer_queue import AnswerQueue

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    queue = get_answer_queue(request)
    assert isinstance(queue, AnswerQueue)
    assert get_answer_queue(request) is queue


@pytest.mark.db
@needs_db
def test_the_link_lookup_finds_only_the_organisation(make_survey):
    # The one query before the tenant is known (liana_survey_shared.db.tenant_for_link).
    import psycopg

    from liana_survey_shared.db import tenant_for_link

    survey_id, _, token = make_survey()
    assert tenant_for_link(token) == DEMO_TENANT
    assert tenant_for_link("x" * 22) is None
    # Without a tenant, the same kind of connection still sees no surveys.
    with psycopg.connect(get_settings().database_url) as conn:
        assert conn.execute("select count(*) from surveys").fetchone() == (0,)
