"""GET /api/v1/results/{survey_id}/overview. Needs a migrated Postgres reached as the
app role; the fixtures delete the surveys they create."""

import os
from collections import Counter
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from data_analyzer.domain import TIME_ZONE, score
from data_analyzer.main import app
from liana_survey_shared.db import ping, tenant_connection

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")
DEMO_USER = UUID("00000000-0000-4000-8000-000000000101")
HEADERS = {"X-Tenant-Id": str(DEMO_TENANT), "X-User-Id": str(DEMO_USER)}
needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)

REASONS = ["Too long", "Unclear", "Slow"]
# (segment, nps answer, reasons picked, comment), oldest first. The first seven
# answers are from the previous Helsinki month, the last five from this one.
ANSWERS = [
    ("members", 10, [], None),
    ("members", 9, [], "Great"),
    ("partners", 3, ["Too long", "Slow"], "Long"),
    ("all", 0, ["Too long"], None),
    ("members", 7, [], None),
    ("partners", 6, ["Unclear"], None),
    ("all", 9, [], None),
    ("members", 10, [], None),
    ("partners", 2, ["Too long"], "Hmm"),
    ("partners", 8, [], None),
    ("members", 4, ["Slow", "Too long"], None),
    ("all", 10, [], None),
]
PREVIOUS = 7


def _moments() -> tuple[datetime, datetime]:
    """A moment in the previous Helsinki month and one in this month."""
    now = datetime.now(TIME_ZONE)
    first = now.replace(day=1, hour=12, minute=0, second=0, microsecond=0)
    return first - timedelta(days=10), now


def _delete(survey_id):
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("delete from surveys where id = %s", (survey_id,))


def _make_survey(conn, title, status="live"):
    return conn.execute(
        """insert into surveys (tenant_id, title, type, status)
           values (%s, %s, 'nps', %s) returning id""",
        (DEMO_TENANT, title, status),
    ).fetchone()[0]


def _make_question(conn, survey_id, position, kind, prompt, options=()):
    return conn.execute(
        """insert into questions (tenant_id, survey_id, position, kind, prompt, options)
           values (%s, %s, %s, %s, %s, %s) returning id""",
        (DEMO_TENANT, survey_id, position, kind, prompt, Jsonb(list(options))),
    ).fetchone()[0]


@pytest.fixture
def survey():
    """An NPS survey with a reasons and a text question and 12 answers in two months."""
    previous, current = _moments()
    with tenant_connection(DEMO_TENANT) as conn:
        survey_id = _make_survey(conn, "Overview test")
        nps = _make_question(conn, survey_id, 1, "nps", "Recommend us?")
        reasons = _make_question(conn, survey_id, 2, "reasons", "What went wrong?", REASONS)
        text = _make_question(conn, survey_id, 3, "text", "Anything else?")
        for i, (segment, value, picked, comment) in enumerate(ANSWERS):
            response_id = conn.execute(
                """insert into responses
                     (tenant_id, survey_id, link_token_hash, segment, submitted_at)
                   values (%s, %s, %s, %s, %s) returning id""",
                (DEMO_TENANT, survey_id, f"k{i}", segment, previous if i < PREVIOUS else current),
            ).fetchone()[0]
            conn.execute(
                """insert into answers (tenant_id, response_id, question_id, value_number)
                   values (%s, %s, %s, %s)""",
                (DEMO_TENANT, response_id, nps, value),
            )
            if picked:
                conn.execute(
                    """insert into answers (tenant_id, response_id, question_id, value_choices)
                       values (%s, %s, %s, %s)""",
                    (DEMO_TENANT, response_id, reasons, Jsonb(picked)),
                )
            if comment:
                conn.execute(
                    """insert into answers (tenant_id, response_id, question_id, value_text)
                       values (%s, %s, %s, %s)""",
                    (DEMO_TENANT, response_id, text, comment),
                )
        conn.execute(
            """insert into survey_channel_views (survey_id, tenant_id, channel, view_count)
               values (%s, %s, 'email', 30), (%s, %s, 'qr', 10)""",
            (survey_id, DEMO_TENANT, survey_id, DEMO_TENANT),
        )
    yield survey_id
    _delete(survey_id)


@pytest.fixture
def segmented():
    """Makes an NPS survey with the given responses per stored segment."""
    made = []

    def create(counts):
        with tenant_connection(DEMO_TENANT) as conn:
            survey_id = _make_survey(conn, "Segment rule test")
            nps = _make_question(conn, survey_id, 1, "nps", "Recommend us?")
            i = 0
            for segment, n in counts.items():
                for _ in range(n):
                    i += 1
                    response_id = conn.execute(
                        """insert into responses (tenant_id, survey_id, link_token_hash, segment)
                           values (%s, %s, %s, %s) returning id""",
                        (DEMO_TENANT, survey_id, f"s{i}", segment),
                    ).fetchone()[0]
                    conn.execute(
                        """insert into answers (tenant_id, response_id, question_id, value_number)
                           values (%s, %s, %s, %s)""",
                        (DEMO_TENANT, response_id, nps, i % 11),
                    )
        made.append(survey_id)
        return survey_id

    yield create
    for survey_id in made:
        _delete(survey_id)


@pytest.mark.db
@needs_db
def test_hidden_small_segment_switches_segments_off(segmented):
    survey_id = segmented({"members": 10, "partners": 3})
    body = overview(survey_id).json()
    assert body["responses"] == 13
    assert body["segments"] == [] and body["by_segment"] == []
    assert overview(survey_id, segment="members").status_code == 400


@pytest.mark.db
@needs_db
def test_two_large_segments_are_listed_and_filterable(segmented):
    survey_id = segmented({"members": 5, "volunteers": 5})
    body = overview(survey_id).json()
    assert [s["value"] for s in body["segments"]] == ["members", "volunteers"]
    assert len(body["by_segment"]) == 2
    assert overview(survey_id, segment="volunteers").json()["responses"] == 5


@pytest.fixture
def empty_survey():
    with tenant_connection(DEMO_TENANT) as conn:
        survey_id = _make_survey(conn, "Empty overview test", "draft")
        _make_question(conn, survey_id, 1, "nps", "Recommend us?")
    yield survey_id
    _delete(survey_id)


def overview(survey_id, **params):
    return TestClient(app).get(
        f"/api/v1/results/{survey_id}/overview", params=params, headers=HEADERS
    )


def counts_of(rows):
    return {str(k): n for k, n in Counter(value for _, value, _, _ in rows).items()}


@pytest.mark.db
@needs_db
def test_overview_scores_the_main_question(survey):
    r = overview(survey)
    assert r.status_code == 200
    body = r.json()
    assert body["survey_id"] == str(survey)
    assert (body["title"], body["type"], body["status"]) == ("Overview test", "nps", "live")
    assert body["responses"] == 12
    assert body["views"] == 40
    assert body["response_rate"] == 30
    # The responses came in by link (the default), views by email and QR.
    assert body["channels"] == ["email", "link", "qr"]
    assert body["last_answer_at"] is not None
    assert body["main"]["question_id"] and body["main"]["kind"] == "nps"
    assert body["main"]["counts"] == {str(v): counts_of(ANSWERS).get(str(v), 0) for v in range(11)}
    assert body["main"]["score"] == score("nps", counts_of(ANSWERS))


@pytest.mark.db
@needs_db
def test_change_since_last_month(survey):
    main = overview(survey).json()["main"]
    assert main["change"] == score("nps", counts_of(ANSWERS)) - score(
        "nps", counts_of(ANSWERS[:PREVIOUS])
    )


@pytest.mark.db
@needs_db
def test_segments_follow_the_anonymity_rules(survey):
    body = overview(survey).json()
    # partners (4) and no segment (3) are small, so together they are Other (7).
    assert [(s["value"], s["answers"]) for s in body["segments"]] == [("members", 5), ("other", 7)]
    assert [g["value"] for g in body["by_segment"]] == ["members", "other"]
    members = [row for row in ANSWERS if row[0] == "members"]
    assert body["by_segment"][0]["score"] == score("nps", counts_of(members))
    assert body["by_segment"][0]["answers"] == 5


@pytest.mark.db
@needs_db
def test_small_segment_is_refused(survey):
    r = overview(survey, segment="partners")
    assert r.status_code == 400
    assert r.json()["detail"] == "Segment not available"


@pytest.mark.db
@needs_db
def test_segment_filter_limits_every_number(survey):
    body = overview(survey, segment="members").json()
    members = [row for row in ANSWERS if row[0] == "members"]
    assert body["segment"] == "members"
    assert body["responses"] == 5
    assert body["response_rate"] is None
    assert body["main"]["score"] == score("nps", counts_of(members))
    assert body["questions"][0]["answers"] == 5
    # One member gave reasons, so each reason is 100% of the respondents who gave any.
    assert body["reasons"] == [
        {"label": "Slow", "count": 1, "percent": 100},
        {"label": "Too long", "count": 1, "percent": 100},
    ]
    assert sum(point["answers"] for point in body["trend"]) == 5


@pytest.mark.db
@needs_db
def test_other_segment_filter_adds_up_its_members(survey):
    body = overview(survey, segment="other").json()
    assert body["responses"] == 7


@pytest.mark.db
@needs_db
def test_trend_by_helsinki_month(survey):
    trend = overview(survey).json()["trend"]
    assert len(trend) == 2
    assert trend[0]["month"] < trend[1]["month"]
    assert [point["answers"] for point in trend] == [PREVIOUS, len(ANSWERS) - PREVIOUS]
    assert trend[0]["score"] == score("nps", counts_of(ANSWERS[:PREVIOUS]))
    assert trend[1]["score"] == score("nps", counts_of(ANSWERS[PREVIOUS:]))


@pytest.mark.db
@needs_db
def test_reasons_and_questions_in_order(survey):
    body = overview(survey).json()
    assert [q["kind"] for q in body["questions"]] == ["nps", "reasons", "text"]
    # Too long 4, Slow 2, Unclear 1, of the 5 responses that gave reasons.
    assert body["reasons"] == [
        {"label": "Too long", "count": 4, "percent": 80},
        {"label": "Slow", "count": 2, "percent": 40},
        {"label": "Unclear", "count": 1, "percent": 20},
    ]
    nps, reasons, text = body["questions"]
    assert [o["label"] for o in nps["options"]] == [str(v) for v in range(11)]
    assert nps["answers"] == 12 and nps["average"] is not None
    assert reasons["answers"] == 5
    assert text["options"] == [] and text["answers"] == 3 and text["average"] is None


@pytest.mark.db
@needs_db
def test_overview_of_survey_without_answers(empty_survey):
    body = overview(empty_survey).json()
    assert body["responses"] == 0
    assert body["main"]["score"] is None and body["main"]["change"] is None
    assert body["trend"] == [] and body["by_segment"] == [] and body["segments"] == []
    assert body["response_rate"] is None and body["last_answer_at"] is None
    assert body["channels"] == []


@pytest.mark.db
@needs_db
def test_other_tenant_survey_is_not_found(survey):
    other = {"X-Tenant-Id": str(uuid4()), "X-User-Id": str(DEMO_USER)}
    r = TestClient(app).get(f"/api/v1/results/{survey}/overview", headers=other)
    assert r.status_code == 404
    assert r.json()["detail"] == "Survey not found"
