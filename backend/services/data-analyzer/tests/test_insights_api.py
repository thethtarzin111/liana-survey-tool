"""GET /api/v1/results/{survey_id}/comment-insights. Needs a migrated Postgres reached as
the app role; the fixtures delete the surveys they create."""

import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from data_analyzer.insights.routes import writer
from data_analyzer.main import app
from liana_survey_shared.db import ping, tenant_connection

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")
DEMO_USER = UUID("00000000-0000-4000-8000-000000000101")
HEADERS = {"X-Tenant-Id": str(DEMO_TENANT), "X-User-Id": str(DEMO_USER)}
needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)

# (segment, nps answer, comment), oldest first.
ANSWERS = [
    ("members", 2, "Membership price went up, call me on +358 40 123 4567"),
    ("members", 4, "The fee is too high for what we get"),
    ("members", 10, "The autumn events were great"),
    ("members", 9, "Lovely events and a friendly atmosphere"),
    ("members", 8, "Price is fine"),
    ("members", 6, None),
    ("guests", 10, "Great evening event"),
    ("guests", 3, "   "),
]


class RecordingWriter:
    """The mock writer, recording what it was sent."""

    name = "Recording"

    def __init__(self):
        from data_analyzer.insights.adapters import MockThemeWriter

        self.inner = MockThemeWriter()
        self.sent = []

    def describe(self, comments, known_themes):
        self.sent.append((comments, known_themes))
        return self.inner.describe(comments, known_themes)


@pytest.fixture
def recording():
    rec = RecordingWriter()
    app.dependency_overrides[writer] = lambda: rec
    yield rec
    app.dependency_overrides.pop(writer, None)


def _question(conn, survey_id, position, kind, prompt, options=()):
    return conn.execute(
        """insert into questions (tenant_id, survey_id, position, kind, prompt, options)
           values (%s, %s, %s, %s, %s, %s) returning id""",
        (DEMO_TENANT, survey_id, position, kind, prompt, Jsonb(list(options))),
    ).fetchone()[0]


@pytest.fixture
def survey():
    """An NPS survey with reasons and a comment question, and 8 responses."""
    with tenant_connection(DEMO_TENANT) as conn:
        survey_id = conn.execute(
            """insert into surveys (tenant_id, title, type, status)
               values (%s, 'Insights test', 'nps', 'live') returning id""",
            (DEMO_TENANT,),
        ).fetchone()[0]
        nps = _question(conn, survey_id, 1, "nps", "Recommend us?")
        _question(conn, survey_id, 2, "reasons", "Why?", ["Events", "Membership fee"])
        text = _question(conn, survey_id, 3, "text", "Anything else?")
        for i, (segment, value, comment) in enumerate(ANSWERS):
            response_id = conn.execute(
                """insert into responses (tenant_id, survey_id, link_token_hash, segment,
                                          submitted_at)
                   values (%s, %s, %s, %s, now() - make_interval(hours => %s)) returning id""",
                (DEMO_TENANT, survey_id, f"i{i}", segment, len(ANSWERS) - i),
            ).fetchone()[0]
            conn.execute(
                """insert into answers (tenant_id, response_id, question_id, value_number)
                   values (%s, %s, %s, %s)""",
                (DEMO_TENANT, response_id, nps, value),
            )
            if comment is not None:
                conn.execute(
                    """insert into answers (tenant_id, response_id, question_id, value_text)
                       values (%s, %s, %s, %s)""",
                    (DEMO_TENANT, response_id, text, comment),
                )
    yield survey_id
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("delete from surveys where id = %s", (survey_id,))


@needs_db
def test_themes_of_the_survey_comments(survey, recording):
    res = TestClient(app).get(f"/api/v1/results/{survey}/comment-insights", headers=HEADERS)
    assert res.status_code == 200
    body = res.json()
    assert (body["status"], body["mode"], body["kind"]) == ("ready", "direct", "nps")
    assert (body["comments"], body["redacted"]) == (6, 1)
    assert {t["label"]: t["comments"] for t in body["themes"]} == {
        "Membership fee": 3,
        "Events": 3,
    }

    # The LLM got redacted text, short ids and the survey's reasons, nothing else.
    ((sent, known),) = recording.sent
    assert known == ["Events", "Membership fee"]
    assert sent[0] == {
        "comment_id": "C1",
        "text": "Membership price went up, call me on [hidden]",
    }
    assert all(set(c) == {"comment_id", "text"} for c in sent)

    fee = next(t for t in body["themes"] if t["label"] == "Membership fee")
    assert fee["sentiment"] == {"negative": 2, "neutral": 1, "positive": 0}
    assert all(q["text"] in s for q, s in zip(fee["quotes"], fee["samples"], strict=False))
    assert body["negative_themes"][0]["label"] == "Membership fee"


@needs_db
def test_segment_filter_applies(survey, recording):
    res = TestClient(app).get(
        f"/api/v1/results/{survey}/comment-insights?segment=guests", headers=HEADERS
    )
    # 2 guests is below the anonymity limit, so segments are off for this survey.
    assert res.status_code == 400


@needs_db
def test_too_few_comments(recording):
    with tenant_connection(DEMO_TENANT) as conn:
        survey_id = conn.execute(
            """insert into surveys (tenant_id, title, type, status)
               values (%s, 'Few comments', 'csat', 'live') returning id""",
            (DEMO_TENANT,),
        ).fetchone()[0]
        _question(conn, survey_id, 1, "long_text", "Tell us more")
    try:
        res = TestClient(app).get(f"/api/v1/results/{survey_id}/comment-insights", headers=HEADERS)
        assert res.status_code == 200
        assert res.json()["status"] == "too_few"
        assert res.json()["kind"] is None
        assert recording.sent == []
    finally:
        with tenant_connection(DEMO_TENANT) as conn:
            conn.execute("delete from surveys where id = %s", (survey_id,))


@needs_db
def test_unknown_survey_is_404():
    res = TestClient(app).get(f"/api/v1/results/{uuid4()}/comment-insights", headers=HEADERS)
    assert res.status_code == 404


@needs_db
def test_tell_us_more_comments_are_included(recording):
    # Surveys without a text question keep the "Tell us more" box in
    # responses.comment: insights read it, as the Responses tab does.
    with tenant_connection(DEMO_TENANT) as conn:
        survey_id = conn.execute(
            """insert into surveys (tenant_id, title, type, status)
               values (%s, 'Comment box insights', 'nps', 'live') returning id""",
            (DEMO_TENANT,),
        ).fetchone()[0]
        nps = _question(conn, survey_id, 1, "nps", "Recommend us?")
        for i, (_, value, comment) in enumerate(ANSWERS):
            response_id = conn.execute(
                """insert into responses (tenant_id, survey_id, link_token_hash, comment,
                                          submitted_at)
                   values (%s, %s, %s, %s, now() - make_interval(hours => %s)) returning id""",
                (DEMO_TENANT, survey_id, f"b{i}", comment, len(ANSWERS) - i),
            ).fetchone()[0]
            conn.execute(
                """insert into answers (tenant_id, response_id, question_id, value_number)
                   values (%s, %s, %s, %s)""",
                (DEMO_TENANT, response_id, nps, value),
            )
    try:
        body = (
            TestClient(app)
            .get(f"/api/v1/results/{survey_id}/comment-insights", headers=HEADERS)
            .json()
        )
        assert (body["status"], body["comments"]) == ("ready", 6)
        ((sent, _),) = recording.sent
        assert sent[0]["text"] == "Membership price went up, call me on [hidden]"
    finally:
        with tenant_connection(DEMO_TENANT) as conn:
            conn.execute("delete from surveys where id = %s", (survey_id,))
