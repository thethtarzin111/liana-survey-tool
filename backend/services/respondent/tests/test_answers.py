"""The answer link (#42). Tests marked `db` need a migrated Postgres reached as
the app role; they delete the surveys they create. The queue is a fake."""

import os
import re
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from liana_survey_shared import links
from liana_survey_shared.config import get_settings
from liana_survey_shared.db import ping, tenant_connection
from liana_survey_shared.texts import text
from respondent_service.domain import (
    AnswerProblem,
    check_open,
    form_answers,
    limit_reached,
    one_tap_answer,
)
from respondent_service.main import app
from respondent_service.pages import page, problem, survey_form, thank_you
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


def test_surveys_close_on_their_close_date():
    now = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
    check_open("live", closes_at=now + timedelta(seconds=1), now=now)
    for closes_at in (now, now - timedelta(days=1)):
        with pytest.raises(AnswerProblem, match="closed") as closed:
            check_open("live", closes_at=closes_at, now=now)
        assert closed.value.status_code == 410


def test_full_surveys_take_no_new_readers():
    assert not limit_reached(None, 10_000)
    assert not limit_reached(3, 2)
    assert limit_reached(3, 3)
    with pytest.raises(AnswerProblem, match="all the answers it needs") as full:
        check_open("live", full=True)
    assert full.value.status_code == 410


def test_pages_escape_survey_texts_and_ignore_odd_colours():
    html = thank_you("<script>alert(1)</script>", "red;}</style><script>", "#F0F9F6")
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html
    assert "red;}" not in html
    assert "#F0F9F6" in html
    assert "Your answer was saved." in thank_you("  ", None, None)
    assert "<title>Hi &amp; bye</title>" in page("Hi & bye", "x")


def test_pages_use_the_survey_language():
    finnish = thank_you(None, None, None, "fi")
    assert '<html lang="fi">' in finnish
    assert "Kiitos!" in finnish and "Vastauksesi on tallennettu." in finnish
    # The creator's own message is shown as written.
    assert "Tack för svaret!" in thank_you("Tack för svaret!", None, None, "sv")
    with pytest.raises(AnswerProblem) as closed:
        check_open("closed")
    swedish = problem(closed.value.message("sv"), "sv")
    assert '<html lang="sv">' in swedish
    assert "Vi kunde inte ta emot ditt svar" in swedish
    assert "Den här enkäten är stängd" in swedish
    # Unknown languages fall back to English.
    assert '<html lang="en">' in thank_you(None, None, None, "de")


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

    def create(
        status="live",
        kind="nps",
        survey_type="nps",
        thank_you_text="Thanks a lot!",
        newsletter_links=False,
        closes_at=None,
        response_limit=None,
        language="en",
    ):
        token = secrets.token_urlsafe(16)
        with tenant_connection(DEMO_TENANT) as conn:
            survey_id = conn.execute(
                """insert into surveys
                     (tenant_id, title, type, status, thank_you, link_token, newsletter_links,
                      closes_at, response_limit, language)
                   values (%s, 'Answer test', %s, %s, %s, %s, %s, %s, %s, %s) returning id""",
                (
                    DEMO_TENANT,
                    survey_type,
                    status,
                    thank_you_text,
                    token,
                    newsletter_links,
                    closes_at,
                    response_limit,
                    language,
                ),
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
def test_the_segment_from_the_link_is_queued(client, queue, make_survey):
    _, _, token = make_survey()
    assert client.get(link(token, reader="anna", answer=9) + "&seg=members").status_code == 200
    assert client.get(link(token, reader="ben", answer=9)).status_code == 200
    assert [m.segment for m in queue.messages] == ["members", "all"]


@pytest.mark.db
@needs_db
@pytest.mark.parametrize("seg", ["Bad!", "none", "other", "-x"])
def test_an_invalid_or_reserved_segment_shows_the_incomplete_link_page(
    client, queue, make_survey, seg
):
    _, _, token = make_survey(language="en")
    r = client.get(link(token, answer=9) + f"&seg={seg}")
    assert r.status_code == 400
    assert r.headers["content-type"].startswith("text/html")
    assert text("link_not_complete", "en") in r.text
    assert queue.messages == []


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


# --- Newsletter snippet links (#40) -------------------------------------------------


def snippet_link(token, reader="12345", answer=9):
    settings = get_settings()
    url = links.snippet_link(settings.public_base_url, token, reader, "spring", "members")
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}&a={answer}"


@pytest.mark.db
@needs_db
def test_a_tap_from_the_newsletter_snippet_is_queued_and_counted_per_reader(
    client, queue, make_survey
):
    survey_id, main_id, token = make_survey(newsletter_links=True)
    r = client.get(snippet_link(token))
    assert r.status_code == 200
    assert "Thank you!" in r.text
    [message] = queue.messages
    assert [(a.question_id, a.number) for a in message.answers] == [(main_id, 9)]
    # The same reader key as a signed link for that contact: counted once either way.
    secret = get_settings().link_signing_secret
    assert message.link_token_hash == links.response_key(secret, token, "12345")
    assert "12345" not in message.model_dump_json()


@pytest.mark.db
@needs_db
def test_a_snippet_link_lianamailer_did_not_fill_in_is_refused(client, queue, make_survey):
    _, _, token = make_survey(newsletter_links=True)
    # e.g. the snippet opened from the editor preview: the placeholder is still there.
    r = client.get(snippet_link(token, reader="$id$"))
    assert r.status_code == 400
    assert "not complete or not valid" in r.text
    assert queue.messages == []


def test_pages_tell_the_browser_there_is_no_icon():
    # Otherwise every answer page also asks the server for /favicon.ico (a 404).
    assert '<link rel="icon" href="data:,">' in page("Hi", "x")


@pytest.mark.db
@needs_db
def test_unsigned_links_are_refused_for_surveys_without_a_snippet(client, queue, make_survey):
    # From review: removing &s= from a signed link must not let anyone answer as anyone.
    _, _, token = make_survey()
    assert client.get(snippet_link(token)).status_code == 400
    unsigned = link(token, answer=9).replace("contact-42", "contact-43")
    unsigned = "&".join(part for part in unsigned.split("&") if not part.startswith("s="))
    r = client.get(unsigned)
    assert r.status_code == 400
    assert "not complete or not valid" in r.text
    assert queue.messages == []


@pytest.mark.db
@needs_db
def test_a_survey_past_its_close_date_takes_no_answers(client, queue, make_survey):
    _, _, token = make_survey(closes_at=datetime.now(UTC) - timedelta(minutes=1))
    r = client.get(link(token, answer=9))
    assert r.status_code == 410
    assert "closed" in r.text
    assert queue.messages == []


@pytest.mark.db
@needs_db
def test_a_full_survey_takes_no_new_readers_but_lets_readers_change_their_answer(
    client, queue, make_survey
):
    survey_id, _, token = make_survey(response_limit=1)
    secret = get_settings().link_signing_secret
    # Anna answered and the worker counted her: the survey is full.
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute(
            """insert into responses (tenant_id, survey_id, link_token_hash)
               values (%s, %s, %s)""",
            (DEMO_TENANT, survey_id, links.response_key(secret, token, "anna")),
        )
        conn.execute(
            """insert into survey_aggregates (survey_id, tenant_id, response_count)
               values (%s, %s, 1)""",
            (survey_id, DEMO_TENANT),
        )
    r = client.get(link(token, reader="ben", answer=9))
    assert r.status_code == 410
    assert "all the answers it needs" in r.text
    assert queue.messages == []

    assert client.get(link(token, reader="anna", answer=7)).status_code == 200
    assert len(queue.messages) == 1


@pytest.mark.db
@needs_db
def test_readers_get_pages_in_the_survey_language(client, queue, make_survey):
    _, _, token = make_survey(thank_you_text=None, language="fi")
    r = client.get(link(token, answer=9))
    assert r.status_code == 200
    assert '<html lang="fi">' in r.text
    assert "Kiitos!" in r.text and "Vastauksesi on tallennettu." in r.text

    _, _, closed = make_survey(status="closed", language="sv")
    r = client.get(link(closed, answer=9))
    assert r.status_code == 410
    assert "Den här enkäten är stängd" in r.text


def views(survey_id):
    with tenant_connection(DEMO_TENANT) as conn:
        rows = conn.execute(
            "select channel::text, view_count from survey_channel_views where survey_id = %s",
            (survey_id,),
        ).fetchall()
    return dict(rows)


@pytest.mark.db
@needs_db
def test_a_reader_counts_as_one_view_however_often_they_tap(client, queue, make_survey):
    survey_id, _, token = make_survey()
    secret = get_settings().link_signing_secret
    # Anna's first tap (a mail scanner, say) was saved already.
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute(
            """insert into responses (tenant_id, survey_id, link_token_hash, channel)
               values (%s, %s, %s, 'email')""",
            (DEMO_TENANT, survey_id, links.response_key(secret, token, "anna")),
        )

    assert client.get(link(token, reader="anna", answer=7)).status_code == 200
    assert views(survey_id) == {}

    assert client.get(link(token, reader="ben", answer=9) + "&ch=qr").status_code == 200
    assert views(survey_id) == {"qr": 1}
    assert [m.channel for m in queue.messages] == ["email", "qr"]


# --- The survey link page (#105) --------------------------------------------------

Q_MAIN = UUID("00000000-0000-4000-8000-0000000000a1")
Q_REASONS = UUID("00000000-0000-4000-8000-0000000000a2")
Q_TEXT = UUID("00000000-0000-4000-8000-0000000000a3")


def question(id, kind, options=(), required=True, prompt="?"):
    return {
        "id": id,
        "kind": kind,
        "prompt": prompt,
        "options": list(options),
        "required": required,
    }


THUMBS = [
    question(Q_MAIN, "thumbs", prompt="How was this newsletter?"),
    question(Q_REASONS, "reasons", ["Too long", "Not relevant"], prompt="What went wrong?"),
    question(Q_TEXT, "long_text", required=False, prompt="Anything else?"),
]


def form(**answers):
    """form(main=["0"]) as the page's fields: q-<question id> per question."""
    ids = {"main": Q_MAIN, "reasons": Q_REASONS, "text": Q_TEXT}
    return {f"q-{ids[name]}": values for name, values in answers.items()}


def test_link_page_answers_are_checked_against_their_questions():
    answers = form_answers("thumbs", THUMBS, form(main=["0"], reasons=["Too long"], text=[" Hi "]))
    assert [(a.number, a.choices, a.text) for a in answers] == [
        (0, None, None),
        (None, ["Too long"], None),
        (None, None, "Hi"),
    ]
    # Optional questions can be left blank.
    blank_text = form(main=["0"], reasons=["Too long"], text=[""])
    assert len(form_answers("thumbs", THUMBS, blank_text)) == 2


def test_thumbs_reasons_count_only_after_not_for_me():
    # As in the email flow: reasons are asked only after "Not for me".
    answers = form_answers("thumbs", THUMBS, form(main=["2"], reasons=["Too long"]))
    assert [a.question_id for a in answers] == [Q_MAIN]
    # NPS and CSAT surveys always ask their reasons.
    nps = [question(Q_MAIN, "nps"), question(Q_REASONS, "reasons", ["Price"])]
    with pytest.raises(AnswerProblem, match="not marked optional"):
        form_answers("nps", nps, form(main=["9"]))


@pytest.mark.parametrize(
    "sent",
    [
        form(main=["3"]),  # not on the thumbs scale
        form(main=["0", "1"]),  # two answers to a one-answer question
        form(main=["0"], reasons=["Something else"]),  # not one of the choices
        form(main=["0"], reasons=["Too long"], text=["x" * 5001]),  # too long
    ],
)
def test_link_page_answers_that_do_not_fit_are_refused(sent):
    with pytest.raises(AnswerProblem, match="could not be read") as refused:
        form_answers("thumbs", THUMBS, sent)
    assert refused.value.status_code == 400


def test_link_page_needs_the_required_answers():
    with pytest.raises(AnswerProblem, match="not marked optional"):
        form_answers("thumbs", THUMBS, form(main=[" "]))
    everything_optional = [question(Q_TEXT, "text", required=False)]
    with pytest.raises(AnswerProblem, match="not marked optional"):
        form_answers("custom", everything_optional, form(text=[""]))


def survey(**changes):
    return {
        "type": "thumbs",
        "title": "Internal name",
        "reader_title": "How was it?",
        "description": "Two minutes.",
        "language": "en",
        "accent_color": "#123456",
        "background_color": "#FFFFFF",
        **changes,
    }


def test_the_link_page_shows_the_reader_title_never_a_template_name():
    page_html = survey_form(survey(), THUMBS, key="k", channel="qr")
    assert "<h1>How was it?</h1>" in page_html and "Two minutes." in page_html
    assert "Internal name" not in page_html
    assert '<input type="hidden" name="ch" value="qr">' in page_html
    assert "Only if you chose “Not for me”." in page_html
    assert 'Anything else? <span class="optional">(optional)</span>' in page_html
    # Without a reader title there is no heading at all, and still no private name.
    untitled = survey_form(survey(reader_title=None), THUMBS, key="k", channel="link")
    assert "<h1>" not in untitled and "Internal name" not in untitled
    assert "<title>Survey</title>" in untitled
    # Custom surveys show their own title.
    custom = survey_form(survey(type="custom"), [], key="k", channel="link")
    assert "<h1>Internal name</h1>" in custom


def test_reasons_without_a_heading_get_one_for_their_survey_type():
    # "+ Add reason" in Edit and preview saves the reasons without a heading.
    unnamed = [THUMBS[0], {**THUMBS[1], "prompt": ""}]
    assert "What went wrong?" in survey_form(survey(), unnamed, key="k", channel="link")
    swedish = survey_form(survey(type="nps", language="sv"), unnamed, key="k", channel="link")
    assert "Vad är främsta skälet till ditt betyg?" in swedish


def test_the_link_page_escapes_texts_and_keeps_sent_answers():
    nasty = [question(Q_MAIN, "single_choice", ['<b>"Yes"</b>'], prompt="<iframe>")]
    page_html = survey_form(
        survey(reader_title="<img>", description="</p>"),
        nasty,
        key="k",
        channel="link",
        sent={f"q-{Q_MAIN}": ['<b>"Yes"</b>']},
        error="Fix it",
    )
    assert "<iframe>" not in page_html and "&lt;iframe&gt;" in page_html
    assert "<img>" not in page_html and "<b>" not in page_html
    assert 'value="&lt;b&gt;&quot;Yes&quot;&lt;/b&gt;" checked' in page_html
    assert '<p class="error" role="alert">Fix it</p>' in page_html


def test_the_link_page_uses_the_survey_language():
    rating = question(Q_TEXT, "rating")
    page_html = survey_form(survey(language="fi"), [*THUMBS, rating], key="k", channel="link")
    assert '<html lang="fi">' in page_html
    assert "Ei minulle" in page_html and "Erittäin tyytyväinen" in page_html
    assert "Lähetä" in page_html


def test_the_link_page_has_a_progress_bar_for_browsers_with_javascript():
    # Hidden in the HTML: the script shows and fills it (#8).
    page_html = survey_form(survey(language="sv"), THUMBS, key="k", channel="link")
    assert 'role="progressbar"' in page_html and 'aria-label="Framsteg"' in page_html
    assert 'data-template="{answered} av {total} besvarade" hidden>' in page_html
    assert "<script>" in page_html and "querySelector('.progress')" in page_html
    # Other pages have no script.
    assert "<script>" not in thank_you(None, None, None)


def add_questions(survey_id, *questions):
    with tenant_connection(DEMO_TENANT) as conn:
        for position, (kind, prompt, options, required) in enumerate(questions, start=2):
            conn.execute(
                """insert into questions
                     (tenant_id, survey_id, position, kind, prompt, options, required)
                   values (%s, %s, %s, %s, %s, %s, %s)""",
                (DEMO_TENANT, survey_id, position, kind, prompt, Jsonb(options), required),
            )


def visit_key(page_html):
    return re.search(r'name="key" value="([^"]+)"', page_html).group(1)


def question_id(survey_id, position):
    with tenant_connection(DEMO_TENANT) as conn:
        return conn.execute(
            "select id from questions where survey_id = %s and position = %s",
            (survey_id, position),
        ).fetchone()[0]


@pytest.mark.db
@needs_db
def test_the_plain_link_shows_the_whole_survey_and_counts_the_visit(client, queue, make_survey):
    survey_id, _, token = make_survey()
    add_questions(survey_id, ("reasons", "Main reason?", ["Price", "Service"], True))
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute(
            "update surveys set reader_title = 'Your view', description = 'Short' where id = %s",
            (survey_id,),
        )
    r = client.get(f"/r/{token}?ch=qr")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    assert "<h1>Your view</h1>" in r.text and "Answer test" not in r.text
    assert "Main?" in r.text and "Main reason?" in r.text and "Service" in r.text
    assert views(survey_id) == {"qr": 1}
    assert queue.messages == []
    # Each visit gets its own key.
    assert visit_key(r.text) != visit_key(client.get(f"/r/{token}").text)


@pytest.mark.db
@needs_db
def test_link_page_answers_are_queued_with_their_channel(client, queue, make_survey):
    survey_id, main_id, token = make_survey()
    add_questions(survey_id, ("text", "Why?", [], False))
    why_id = question_id(survey_id, 2)
    key = visit_key(client.get(f"/r/{token}?ch=qr").text)
    sent = {"key": key, "ch": "qr", f"q-{main_id}": "9", f"q-{why_id}": "Great"}
    r = client.post(f"/r/{token}", data=sent)
    assert r.status_code == 200
    assert "Thanks a lot!" in r.text
    [message] = queue.messages
    assert message.channel == "qr"
    assert [(a.question_id, a.number, a.text) for a in message.answers] == [
        (main_id, 9, None),
        (why_id, None, "Great"),
    ]
    # Sending again from the same visit is the same reader, so it replaces the answer.
    client.post(f"/r/{token}", data={"key": key, f"q-{main_id}": "10"})
    assert queue.messages[1].link_token_hash == message.link_token_hash
    assert queue.messages[1].channel == "link"


@pytest.mark.db
@needs_db
def test_link_page_answers_that_do_not_fit_show_the_form_again(client, queue, make_survey):
    _, main_id, token = make_survey()
    key = visit_key(client.get(f"/r/{token}").text)
    r = client.post(f"/r/{token}", data={"key": key, f"q-{main_id}": "11"})
    assert r.status_code == 400
    assert "could not be read" in r.text
    assert visit_key(r.text) == key
    r = client.post(f"/r/{token}", data={"key": key})
    assert r.status_code == 400 and "not marked optional" in r.text
    assert queue.messages == []


@pytest.mark.db
@needs_db
def test_link_page_answers_need_a_visit_key_from_this_survey(client, queue, make_survey):
    _, main_id, token = make_survey()
    _, _, other = make_survey()
    secret = get_settings().link_signing_secret
    # An email reader's signed id must not let the page replace their answer.
    email_reader = f"contact-42.{links.signature(secret, token, 'contact-42')}"
    other_visit = visit_key(client.get(f"/r/{other}").text)
    for key in ("", "web-made-up.sig", other_visit, email_reader):
        r = client.post(f"/r/{token}", data={"key": key, f"q-{main_id}": "9"})
        assert r.status_code == 400, key
        assert "not complete or not valid" in r.text
    assert queue.messages == []


@pytest.mark.db
@needs_db
def test_closed_and_full_surveys_show_why_instead_of_the_form(client, queue, make_survey):
    survey_id, main_id, token = make_survey()
    key = visit_key(client.get(f"/r/{token}").text)
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("update surveys set status = 'closed' where id = %s", (survey_id,))
    r = client.post(f"/r/{token}", data={"key": key, f"q-{main_id}": "9"})
    assert r.status_code == 410 and "closed" in r.text
    assert client.get(f"/r/{token}").status_code == 410

    _, _, full = make_survey(response_limit=1, language="sv")
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute(
            """insert into survey_aggregates (survey_id, tenant_id, response_count)
               select id, tenant_id, 1 from surveys where link_token = %s""",
            (full,),
        )
    r = client.get(f"/r/{full}")
    assert r.status_code == 410 and "Enkäten har fått alla svar" in r.text
    assert queue.messages == []
