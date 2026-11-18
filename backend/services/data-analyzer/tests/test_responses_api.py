"""GET /api/v1/results/{survey_id}/responses, its detail and its CSV. Needs a migrated
Postgres reached as the app role; the fixtures delete the surveys they create."""

import csv
import io
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from data_analyzer import repo
from data_analyzer.domain import EMAIL_PATTERN, PHONE_PATTERN, display_id, mask
from data_analyzer.main import app
from liana_survey_shared.db import ping, tenant_connection

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")
DEMO_USER = UUID("00000000-0000-4000-8000-000000000101")
HEADERS = {"X-Tenant-Id": str(DEMO_TENANT), "X-User-Id": str(DEMO_USER)}
needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)
EMAIL_COMMENT = "Mail me at anna.virtanen@example.org thanks"
PHONE_COMMENT = "Call +358 40 123 4567 please"
# (segment, nps answer, reasons picked, comment, long text), oldest first.
ANSWERS = [
    ("members", 10, [], EMAIL_COMMENT, None),
    ("partners", 3, ["Too long", "Slow"], "Long", "Details: 040-1234567"),
    ("members", 9, [], None, None),
    ("partners", 6, ["Unclear"], PHONE_COMMENT, None),
    ("members", 7, [], "Fine thanks", None),
    ("partners", 2, ["Too long"], None, None),
    ("members", 8, [], None, None),
    ("partners", 0, ["Slow"], "Hmm", None),
    ("members", 10, [], None, None),
    ("partners", 5, [], "Too slow", None),
]


def _delete(survey_id):
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("delete from surveys where id = %s", (survey_id,))


def _make_survey(conn, title="Responses test"):
    return conn.execute(
        "insert into surveys (tenant_id, title, type, status) values (%s, %s, 'nps', 'live')"
        " returning id",
        (DEMO_TENANT, title),
    ).fetchone()[0]


def _make_question(conn, survey_id, position, kind, prompt, options=()):
    return conn.execute(
        """insert into questions (tenant_id, survey_id, position, kind, prompt, options)
           values (%s, %s, %s, %s, %s, %s) returning id""",
        (DEMO_TENANT, survey_id, position, kind, prompt, Jsonb(list(options))),
    ).fetchone()[0]


def _make_response(conn, survey_id, i, segment, submitted_at, contact_ref=None):
    return conn.execute(
        """insert into responses
             (tenant_id, survey_id, link_token_hash, segment, submitted_at, contact_ref)
           values (%s, %s, %s, %s, %s, %s) returning id""",
        (DEMO_TENANT, survey_id, f"secret-hash-{i}", segment, submitted_at, contact_ref),
    ).fetchone()[0]


def _answer(conn, response_id, question_id, number=None, text=None, choices=None):
    conn.execute(
        """insert into answers
             (tenant_id, response_id, question_id, value_number, value_text, value_choices)
           values (%s, %s, %s, %s, %s, %s)""",
        (
            DEMO_TENANT,
            response_id,
            question_id,
            number,
            text,
            Jsonb(choices) if choices is not None else None,
        ),
    )


@pytest.fixture
def survey():
    """An NPS survey: nps, reasons, text and long text questions, 10 answers in two
    segments, ten minutes apart. The oldest answer carries a contact_ref."""
    start = datetime.now(UTC) - timedelta(hours=3)
    made = {}
    with tenant_connection(DEMO_TENANT) as conn:
        survey_id = _make_survey(conn)
        nps = _make_question(conn, survey_id, 1, "nps", "Recommend us?")
        reasons = _make_question(conn, survey_id, 2, "reasons", "What went wrong?", ["Too long"])
        text = _make_question(conn, survey_id, 3, "text", "Anything else?")
        long_text = _make_question(conn, survey_id, 4, "long_text", "Tell us more")
        for i, (segment, value, picked, comment, long) in enumerate(ANSWERS):
            rid = _make_response(
                conn,
                survey_id,
                i,
                segment,
                start + timedelta(minutes=10 * i),
                contact_ref="C-1" if i == 0 else None,
            )
            made[i] = rid
            _answer(conn, rid, nps, number=value)
            if picked:
                _answer(conn, rid, reasons, choices=picked)
            if comment:
                _answer(conn, rid, text, text=comment)
            if long:
                _answer(conn, rid, long_text, text=long)
    yield survey_id, made
    _delete(survey_id)


@pytest.fixture
def segmented():
    """Makes an NPS survey with the given responses per stored segment."""
    made = []

    def create(counts):
        with tenant_connection(DEMO_TENANT) as conn:
            survey_id = _make_survey(conn, "Segment label test")
            nps = _make_question(conn, survey_id, 1, "nps", "Recommend us?")
            i = 0
            for segment, n in counts.items():
                for _ in range(n):
                    i += 1
                    rid = _make_response(conn, survey_id, i, segment, datetime.now(UTC))
                    _answer(conn, rid, nps, number=i % 11)
        made.append(survey_id)
        return survey_id

    yield create
    for survey_id in made:
        _delete(survey_id)


def responses(survey_id, **params):
    return TestClient(app).get(
        f"/api/v1/results/{survey_id}/responses", params=params, headers=HEADERS
    )


def detail(survey_id, response_id):
    return TestClient(app).get(
        f"/api/v1/results/{survey_id}/responses/{response_id}", headers=HEADERS
    )


def export(survey_id, **params):
    return TestClient(app).get(
        f"/api/v1/results/{survey_id}/responses.csv", params=params, headers=HEADERS
    )


@pytest.mark.db
@needs_db
def test_rows_newest_first_with_masking(survey):
    survey_id, made = survey
    r = responses(survey_id)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 10
    assert [row["id"] for row in body["rows"]] == [str(made[i]) for i in range(9, -1, -1)]
    first = body["rows"][-1]
    assert first == {
        "id": str(made[0]),
        "display_id": display_id(made[0]),
        "submitted_at": first["submitted_at"],
        "answer": 10,
        "reason": None,
        "comment": "Mail me at [hidden] thanks",
        "masked": True,
        "segment_label": "Members",
    }
    by_id = {row["id"]: row for row in body["rows"]}
    second = by_id[str(made[1])]
    assert (second["answer"], second["reason"], second["comment"], second["masked"]) == (
        3,
        "Too long; Slow",
        "Long",
        False,
    )
    assert by_id[str(made[3])]["comment"] == "Call [hidden] please"
    assert by_id[str(made[2])]["comment"] is None and by_id[str(made[2])]["masked"] is False


@pytest.mark.db
@needs_db
def test_paging(survey):
    survey_id, made = survey
    page = responses(survey_id, limit=3, offset=3).json()
    assert page["total"] == 10
    assert [row["id"] for row in page["rows"]] == [str(made[i]) for i in (6, 5, 4)]
    assert responses(survey_id, limit=201).status_code == 422
    assert responses(survey_id, limit=0).status_code == 422
    assert responses(survey_id, offset=-1).status_code == 422


@pytest.mark.db
@needs_db
def test_search_does_not_reveal_masked_text(survey):
    survey_id, made = survey
    assert responses(survey_id, q="example.org").json()["total"] == 0
    assert responses(survey_id, q="anna").json()["total"] == 0
    assert responses(survey_id, q="1234").json()["total"] == 0
    found = responses(survey_id, q="THANKS").json()
    assert found["total"] == 2
    assert {row["comment"] for row in found["rows"]} == {
        "Mail me at [hidden] thanks",
        "Fine thanks",
    }
    # % and _ are plain characters in a search.
    assert responses(survey_id, q="%").json()["total"] == 0
    assert responses(survey_id, q="_").json()["total"] == 0


@pytest.mark.db
@needs_db
def test_group_filter(survey):
    survey_id, _ = survey
    body = responses(survey_id, group="detractors").json()
    assert sorted(row["answer"] for row in body["rows"]) == [0, 2, 3, 5, 6]
    assert body["total"] == 5
    assert responses(survey_id, group="promoters").json()["total"] == 3
    assert responses(survey_id, group="nope").status_code == 422
    # Another scale's group is not a group of this survey.
    assert responses(survey_id, group="good").status_code == 422
    both = responses(survey_id, group="detractors", q="slow").json()
    assert [row["comment"] for row in both["rows"]] == ["Too slow"]


@pytest.mark.db
@needs_db
def test_segment_filter_and_errors(survey):
    survey_id, _ = survey
    members = responses(survey_id, segment="members").json()
    assert members["total"] == 5
    assert {row["segment_label"] for row in members["rows"]} == {"Members"}
    assert responses(survey_id, segment="all").json()["total"] == 10
    assert responses(survey_id, segment="nobody").status_code == 400
    assert responses(uuid4()).status_code == 404
    assert detail(uuid4(), uuid4()).status_code == 404
    assert export(uuid4()).status_code == 404
    assert responses("not-a-uuid").status_code == 422


@pytest.mark.db
@needs_db
def test_small_segment_is_refused(segmented):
    survey_id = segmented({"members": 10, "partners": 3})
    assert responses(survey_id, segment="partners").status_code == 400
    assert export(survey_id, segment="partners").status_code == 400
    assert responses(survey_id, segment="other").status_code == 400


@pytest.mark.db
@needs_db
def test_segment_label_is_null_when_segments_are_off(segmented):
    survey_id = segmented({"members": 10, "partners": 3})
    body = responses(survey_id).json()
    assert body["total"] == 13
    assert {row["segment_label"] for row in body["rows"]} == {None}
    row = body["rows"][0]
    assert detail(survey_id, row["id"]).json()["segment_label"] is None
    cells = list(csv.reader(io.StringIO(export(survey_id).text)))
    assert cells[0][:3] == ["ID", "Received", "Segment"]
    assert {line[2] for line in cells[1:]} == {""}


@pytest.mark.db
@needs_db
def test_segment_label_other_for_small_segments(segmented):
    survey_id = segmented({"members": 5, "partners": 3, "volunteers": 2, "all": 5})
    body = responses(survey_id, limit=200).json()
    assert body["total"] == 15
    labels = sorted(row["segment_label"] for row in body["rows"])
    assert labels == ["Members"] * 5 + ["No segment"] * 5 + ["Other"] * 5
    other = responses(survey_id, segment="other", limit=200).json()
    assert other["total"] == 5 and {r["segment_label"] for r in other["rows"]} == {"Other"}
    assert responses(survey_id, segment="none").json()["total"] == 5


@pytest.mark.db
@needs_db
def test_detail_lists_every_answer_masked(survey):
    survey_id, made = survey
    r = detail(survey_id, made[1])
    assert r.status_code == 200
    body = r.json()
    assert body["display_id"] == display_id(made[1])
    assert body["segment_label"] == "Partners"
    assert [(a["prompt"], a["kind"], a["value"], a["masked"]) for a in body["answers"]] == [
        ("Recommend us?", "nps", 3, False),
        ("What went wrong?", "reasons", ["Too long", "Slow"], False),
        ("Anything else?", "text", "Long", False),
        ("Tell us more", "long_text", "Details: [hidden]", True),
    ]
    assert all(a["question_id"] for a in body["answers"])
    # A question without an answer is listed with no value.
    empty = detail(survey_id, made[2]).json()["answers"]
    assert [a["value"] for a in empty] == [9, None, None, None]
    assert detail(survey_id, uuid4()).status_code == 404
    assert detail(survey_id, "not-a-uuid").status_code == 422


@pytest.mark.db
@needs_db
def test_detail_of_another_survey_is_not_found(survey, segmented):
    _, made = survey
    other = segmented({"members": 5, "partners": 5})
    assert detail(other, made[0]).status_code == 404


@pytest.mark.db
@needs_db
def test_csv_is_masked(survey):
    survey_id, made = survey
    r = export(survey_id)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert "[hidden]" in r.text
    assert "example.org" not in r.text and "123 4567" not in r.text and "1234567" not in r.text
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == [
        "ID",
        "Received",
        "Segment",
        "Recommend us?",
        "What went wrong?",
        "Anything else?",
        "Tell us more",
    ]
    assert len(rows) == 11
    newest, oldest = rows[1], rows[-1]
    assert newest[0] == display_id(made[9]) and newest[2] == "Partners"
    assert oldest[0] == display_id(made[0])
    assert oldest[3:] == ["10", "", "Mail me at [hidden] thanks", ""]
    by_id = {row[0]: row for row in rows[1:]}
    assert by_id[display_id(made[1])][3:] == ["3", "Too long; Slow", "Long", "Details: [hidden]"]


@pytest.mark.db
@needs_db
def test_csv_follows_the_filters(survey):
    survey_id, _ = survey
    rows = list(
        csv.reader(io.StringIO(export(survey_id, segment="members", group="promoters", q="").text))
    )
    assert [r[3] for r in rows[1:]] == ["10", "9", "10"]
    assert len(list(csv.reader(io.StringIO(export(survey_id, q="example.org").text)))) == 1
    assert export(survey_id, group="nope").status_code == 422


@pytest.mark.db
@needs_db
def test_csv_does_not_run_as_a_formula(segmented):
    survey_id = segmented({"members": 5, "partners": 5})
    with tenant_connection(DEMO_TENANT) as conn:
        text = _make_question(conn, survey_id, 2, "text", "Anything else?")
        rid = conn.execute(
            "select id from responses where survey_id = %s limit 1", (survey_id,)
        ).fetchone()[0]
        _answer(conn, rid, text, text='=HYPERLINK("http://example.invalid")')
    rows = list(csv.reader(io.StringIO(export(survey_id).text)))
    assert '\'=HYPERLINK("http://example.invalid")' in [row[4] for row in rows[1:]]


@pytest.mark.db
@needs_db
def test_no_contact_ref_anywhere(survey):
    survey_id, made = survey
    bodies = [
        responses(survey_id, limit=200).text,
        detail(survey_id, made[0]).text,
        export(survey_id).text,
    ]
    for body in bodies:
        assert "C-1" not in body
        assert "contact_ref" not in body
        assert "secret-hash" not in body and "link_token_hash" not in body


@pytest.mark.db
@needs_db
def test_empty_survey_and_paths_do_not_collide(survey):
    with tenant_connection(DEMO_TENANT) as conn:
        empty = _make_survey(conn, "Empty responses test")
        _make_question(conn, empty, 1, "nps", "Recommend us?")
    try:
        assert responses(empty).json() == {"total": 0, "rows": []}
        assert export(empty).text.splitlines() == ["ID,Received,Segment,Recommend us?"]
    finally:
        _delete(empty)


SAMPLES = [
    "Mail me at anna.virtanen@example.org thanks",
    "Call +358 40 123 4567 or 040-1234567",
    "Room 12, 3 people, 2026",
    "(09) 123 4567",
    "tel 09 123 4567.",
    "+44 20 7946 0958",
    "00358 40 123 4567",
    "a@b.fi, c.d+tag@mail.example.com",
    "Date 2026-11-19, 10 000 people",
    "Order 1234567 and 12345",
    "line one\n0401234567\nline three",
    "0401234567,0401234567",
    "0401234567 0401234567 0401234567",
    "x@y.zz0401234567",
    "no at sign example.org",
    "100% sure_ ok",
    "ääkköset anna.ä@example.org",
    "",
]


@pytest.mark.db
@needs_db
@pytest.mark.parametrize("text", SAMPLES)
def test_sql_masks_the_same_strings_as_python(text):
    with tenant_connection(DEMO_TENANT) as conn:
        sql = conn.execute(
            f"select {repo.mask_sql('%(text)s::text')} as masked",
            {"text": text, "email": EMAIL_PATTERN, "phone": PHONE_PATTERN},
        ).fetchone()[0]
    assert sql == mask(text)[0]
