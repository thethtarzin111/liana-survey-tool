"""Tests for /api/v1/surveys.

Validation tests run anywhere. Tests marked `db` need a migrated Postgres
reached as the app role (so row-level security applies), e.g. in CI's db job:

    DATABASE_URL=postgresql://survey_app:...@localhost:5432/survey pytest -m db

They are skipped when no database answers, unless REQUIRE_DB=1 (set in CI),
so CI can never pass by silently skipping them.
"""

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from liana_survey_shared.db import ping
from liana_survey_shared.web.auth import CurrentUser, current_user
from liana_survey_shared.web.db import tenant_db
from survey_manager.main import app

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")
OTHER_TENANT = UUID("00000000-0000-4000-8000-0000000000ff")

needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)


def as_user(tenant_id: UUID) -> CurrentUser:
    return CurrentUser(
        user_id=uuid4(),
        tenant_id=tenant_id,
        tenant_name="Test tenant",
        name="Test user",
        email="test@example.org",
    )


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- Validation (no database needed) ----------------------------------------


@pytest.fixture
def no_db(client):
    """Requests fail validation before the handler runs, so no real connection is needed."""
    app.dependency_overrides[tenant_db] = lambda: None
    return client


@pytest.mark.parametrize(
    "body",
    [
        {},  # type is required
        {"type": "quiz"},  # unknown type
        {"type": "nps", "title": "   "},  # blank title
        {"type": "nps", "title": "x" * 81},  # too long
        {"type": "nps", "description": "x" * 1001},  # too long
        {"type": "nps", "status": "live"},  # status is set by the server
        {"type": "nps", "tenant_id": str(OTHER_TENANT)},  # tenant comes from the login
    ],
)
def test_create_rejects_invalid_body(no_db, body):
    assert no_db.post("/api/v1/surveys", json=body).status_code == 422


def test_update_rejects_blank_title_and_unknown_fields(no_db):
    url = f"/api/v1/surveys/{uuid4()}"
    assert no_db.patch(url, json={"title": ""}).status_code == 422
    assert no_db.patch(url, json={"status": "live"}).status_code == 422
    # Explicit null would otherwise be a silent no-op with 200.
    assert no_db.patch(url, json={"title": None}).status_code == 422
    assert no_db.patch(url, json={"type": None}).status_code == 422
    assert no_db.patch(url, json={"description": None}).status_code == 422


def test_update_rejects_too_long_title_and_description(no_db):
    url = f"/api/v1/surveys/{uuid4()}"
    title_error = no_db.patch(url, json={"title": "x" * 81})
    description_error = no_db.patch(url, json={"description": "x" * 1001})

    assert title_error.status_code == 422
    assert title_error.json()["detail"][0]["loc"] == ["body", "title"]
    assert "at most 80 characters" in title_error.json()["detail"][0]["msg"]
    assert description_error.status_code == 422
    assert description_error.json()["detail"][0]["loc"] == ["body", "description"]
    assert "at most 1000 characters" in description_error.json()["detail"][0]["msg"]


def test_bad_survey_id_is_422(no_db):
    assert no_db.get("/api/v1/surveys/not-a-uuid").status_code == 422


@pytest.mark.parametrize("query", ["status=archived", "q=" + "x" * 201])
def test_list_rejects_unknown_status_and_long_search(no_db, query):
    assert no_db.get(f"/api/v1/surveys?{query}").status_code == 422


def test_action_routes_reject_bad_survey_id(no_db):
    for action in ("duplicate", "close", "unpublish"):
        assert no_db.post(f"/api/v1/surveys/not-a-uuid/{action}").status_code == 422
    assert no_db.delete("/api/v1/surveys/not-a-uuid").status_code == 422


# --- With a database ------------------------------------------------------


@pytest.mark.db
@needs_db
def test_new_survey_is_a_draft_with_default_title(client):
    r = client.post("/api/v1/surveys", json={"type": "nps"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "draft"
    assert body["type"] == "nps"
    assert body["title"] == "Untitled survey"
    assert body["description"] is None
    assert body["anonymous"] is True


@pytest.mark.db
@needs_db
@pytest.mark.parametrize("kind", ["thumbs", "nps", "csat", "custom"])
def test_every_wizard_type_can_be_created(client, kind):
    r = client.post("/api/v1/surveys", json={"type": kind, "title": f"  {kind} test  "})
    assert r.status_code == 201
    assert r.json()["type"] == kind
    assert r.json()["title"] == f"{kind} test"  # surrounding spaces trimmed


@pytest.mark.db
@needs_db
def test_created_survey_is_listed_and_can_be_reopened(client):
    created = client.post(
        "/api/v1/surveys",
        json={
            "type": "csat",
            "title": "Reopen me",
            "description": "  Members' view of 2026  ",
        },
    ).json()
    assert created["description"] == "Members' view of 2026"

    listed = client.get("/api/v1/surveys").json()
    assert listed[0]["id"] == created["id"]  # newest first

    r = client.get(f"/api/v1/surveys/{created['id']}")
    assert r.status_code == 200
    assert r.json() == created


@pytest.mark.db
@needs_db
def test_patch_changes_only_given_fields(client):
    created = client.post("/api/v1/surveys", json={"type": "thumbs"}).json()

    r = client.patch(f"/api/v1/surveys/{created['id']}", json={"title": "Was this useful?"})
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Was this useful?"
    assert body["type"] == "thumbs"
    assert body["updated_at"] >= created["updated_at"]

    r = client.patch(f"/api/v1/surveys/{created['id']}", json={"type": "nps"})
    assert r.json()["type"] == "nps"
    assert r.json()["title"] == "Was this useful?"


@pytest.mark.db
@needs_db
def test_description_can_be_updated_and_cleared(client):
    created = client.post(
        "/api/v1/surveys", json={"type": "nps", "description": "  Initial context  "}
    ).json()
    url = f"/api/v1/surveys/{created['id']}"
    assert created["description"] == "Initial context"

    updated = client.patch(url, json={"description": "  New context  "})
    assert updated.status_code == 200
    assert updated.json()["description"] == "New context"

    cleared = client.patch(url, json={"description": "   "})
    assert cleared.status_code == 200
    assert cleared.json()["description"] is None
    assert client.get(url).json()["description"] is None


@pytest.mark.db
@needs_db
def test_unknown_survey_is_404(client):
    missing = uuid4()
    assert client.get(f"/api/v1/surveys/{missing}").status_code == 404
    assert client.patch(f"/api/v1/surveys/{missing}", json={"title": "x"}).status_code == 404


@pytest.mark.db
@needs_db
def test_other_tenant_cannot_see_or_change_a_survey(client):
    created = client.post("/api/v1/surveys", json={"type": "nps", "title": "Members only"}).json()
    url = f"/api/v1/surveys/{created['id']}"

    app.dependency_overrides[current_user] = lambda: as_user(OTHER_TENANT)
    assert created["id"] not in [s["id"] for s in client.get("/api/v1/surveys").json()]
    assert client.get(url).status_code == 404
    assert client.patch(url, json={"title": "hijacked"}).status_code == 404

    # Back as the demo tenant: unchanged.
    app.dependency_overrides.clear()
    assert client.get(url).json()["title"] == "Members only"


@pytest.mark.db
@needs_db
def test_created_survey_is_committed_when_the_response_arrives(client):
    """Regression: the commit must happen before the response is sent, so a
    client that opens the survey right after creating it never gets 404."""
    from liana_survey_shared.db import tenant_connection

    created = client.post("/api/v1/surveys", json={"type": "nps", "title": "Committed"}).json()
    with tenant_connection(DEMO_TENANT) as conn:
        row = conn.execute("select title from surveys where id = %s", (created["id"],)).fetchone()
    assert row is not None and row[0] == "Committed"


# --- Surveys list: search, filter and actions (#33) ---------------------------


def make_survey(client, title: str, **fields) -> dict:
    """Create a survey, then set columns the API does not let clients set."""
    from liana_survey_shared.db import tenant_connection

    created = client.post("/api/v1/surveys", json={"type": "nps", "title": title}).json()
    if fields:
        sets = ", ".join(f"{name} = %s" for name in fields)
        with tenant_connection(DEMO_TENANT) as conn:
            conn.execute(
                f"update surveys set {sets} where id = %s", (*fields.values(), created["id"])
            )
    return created


def unique(label: str) -> str:
    """A title no other test or seed row uses, so list tests ignore other data."""
    return f"{label} {uuid4().hex[:10]}"


@pytest.mark.db
@needs_db
def test_list_searches_titles_ignoring_case(client):
    token = uuid4().hex[:10]
    match = make_survey(client, f"Member Feedback {token}")
    make_survey(client, unique("Something else"))

    found = client.get("/api/v1/surveys", params={"q": f"  feedback {token.upper()}  "}).json()
    assert [s["id"] for s in found] == [match["id"]]
    assert found[0]["answers"] == 0


@pytest.mark.db
@needs_db
def test_list_search_treats_wildcards_literally(client):
    token = uuid4().hex[:10]
    match = make_survey(client, f"100% {token}")
    make_survey(client, f"100 points {token}")

    found = client.get("/api/v1/surveys", params={"q": f"100% {token}"}).json()
    assert [s["id"] for s in found] == [match["id"]]
    assert client.get("/api/v1/surveys", params={"q": f"1_0 {token}"}).json() == []


@pytest.mark.db
@needs_db
def test_list_filters_by_status_and_combines_with_search(client):
    token = uuid4().hex[:10]
    live = make_survey(client, f"Live {token}", status="live")
    draft = make_survey(client, f"Draft {token}")

    live_ids = [s["id"] for s in client.get("/api/v1/surveys", params={"status": "live"}).json()]
    assert live["id"] in live_ids and draft["id"] not in live_ids
    both = client.get("/api/v1/surveys", params={"q": token, "status": "draft"}).json()
    assert [s["id"] for s in both] == [draft["id"]]


@pytest.mark.db
@needs_db
def test_list_shows_answer_counts_from_totals(client):
    from liana_survey_shared.db import tenant_connection

    survey = make_survey(client, unique("Answered"), status="live")
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute(
            """insert into survey_aggregates (survey_id, tenant_id, response_count, distribution)
               values (%s, %s, 7, '{"9": 4, "10": 1, "7": 1, "3": 1}')""",
            (survey["id"], DEMO_TENANT),
        )
    found = client.get("/api/v1/surveys", params={"q": survey["title"]}).json()
    assert found[0]["answers"] == 7
    # 5 promoters, 1 passive, 1 detractor of 7: NPS +57.
    assert found[0]["headline"] == {"score": "NPS +57", "note": "scale −100 to +100"}


@pytest.mark.db
@needs_db
def test_list_shows_the_last_answer_time(client):
    from liana_survey_shared.db import tenant_connection

    answered = make_survey(client, unique("Last answer"), status="live")
    silent = make_survey(client, unique("No answer"), status="live")
    with tenant_connection(DEMO_TENANT) as conn:
        for token, at in (("a", "2026-11-01T09:00:00Z"), ("b", "2026-11-05T17:30:00Z")):
            conn.execute(
                """insert into responses (tenant_id, survey_id, submitted_at, link_token_hash)
                   values (%s, %s, %s, %s)""",
                (DEMO_TENANT, answered["id"], at, token),
            )
    found = client.get("/api/v1/surveys", params={"q": answered["title"]}).json()
    assert datetime.fromisoformat(found[0]["last_answer_at"]) == datetime(
        2026, 11, 5, 17, 30, tzinfo=UTC
    )
    found = client.get("/api/v1/surveys", params={"q": silent["title"]}).json()
    assert found[0]["last_answer_at"] is None


@pytest.mark.db
@needs_db
def test_list_has_no_headline_before_answers(client):
    survey = make_survey(client, unique("No answers yet"))
    found = client.get("/api/v1/surveys", params={"q": survey["title"]}).json()
    assert found[0]["headline"] is None
    assert "distribution" not in found[0]


@pytest.mark.db
@needs_db
def test_duplicate_copies_survey_and_questions_as_a_draft(client):
    from liana_survey_shared.db import tenant_connection

    original = make_survey(
        client, unique("Event feedback"), status="live", opens_at="2026-12-01T09:00:00Z"
    )
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute(
            """insert into questions (tenant_id, survey_id, position, kind, prompt, required)
               values (%s, %s, 1, 'nps', 'How likely?', true),
                      (%s, %s, 2, 'text', 'Why?', false)""",
            (DEMO_TENANT, original["id"], DEMO_TENANT, original["id"]),
        )

    r = client.post(f"/api/v1/surveys/{original['id']}/duplicate")
    assert r.status_code == 201
    copy = r.json()
    assert copy["id"] != original["id"]
    assert copy["title"] == f"{original['title']} (copy)"
    assert copy["status"] == "draft"
    assert copy["type"] == original["type"]
    assert copy["opens_at"] is None

    with tenant_connection(DEMO_TENANT) as conn:
        rows = conn.execute(
            """select position, kind, prompt, required from questions
               where survey_id = %s order by position""",
            (copy["id"],),
        ).fetchall()
    assert rows == [(1, "nps", "How likely?", True), (2, "text", "Why?", False)]
    assert client.get(f"/api/v1/surveys/{original['id']}").json()["status"] == "live"


@pytest.mark.db
@needs_db
def test_duplicate_keeps_long_titles_within_the_limit(client):
    original = make_survey(client, "x" * 80)
    copy = client.post(f"/api/v1/surveys/{original['id']}/duplicate").json()
    assert len(copy["title"]) == 80
    assert copy["title"].endswith(" (copy)")


@pytest.mark.db
@needs_db
@pytest.mark.parametrize(
    ("action", "start", "end"),
    [
        ("close", "live", "closed"),
        ("unpublish", "live", "draft"),
        ("unpublish", "scheduled", "draft"),
    ],
)
def test_allowed_status_changes(client, action, start, end):
    survey = make_survey(client, unique(f"{action} {start}"), status=start)
    r = client.post(f"/api/v1/surveys/{survey['id']}/{action}")
    assert r.status_code == 200
    assert r.json()["status"] == end
    assert client.get(f"/api/v1/surveys/{survey['id']}").json()["status"] == end


@pytest.mark.db
@needs_db
@pytest.mark.parametrize(
    ("action", "start"),
    [
        ("close", "draft"),
        ("close", "scheduled"),
        ("close", "closed"),
        ("unpublish", "draft"),
        ("unpublish", "closed"),
    ],
)
def test_disallowed_status_changes_are_409_and_change_nothing(client, action, start):
    survey = make_survey(client, unique(f"{action} {start}"), status=start)
    r = client.post(f"/api/v1/surveys/{survey['id']}/{action}")
    assert r.status_code == 409
    assert start in r.json()["detail"]
    assert client.get(f"/api/v1/surveys/{survey['id']}").json()["status"] == start


@pytest.mark.db
@needs_db
def test_delete_removes_the_survey_and_its_questions(client):
    from liana_survey_shared.db import tenant_connection

    survey = make_survey(client, unique("Delete me"))
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute(
            """insert into questions (tenant_id, survey_id, position, kind, prompt)
               values (%s, %s, 1, 'nps', 'How likely?')""",
            (DEMO_TENANT, survey["id"]),
        )
    url = f"/api/v1/surveys/{survey['id']}"

    r = client.delete(url)
    assert r.status_code == 204
    assert r.content == b""
    assert client.get(url).status_code == 404
    assert client.delete(url).status_code == 404
    with tenant_connection(DEMO_TENANT) as conn:
        left = conn.execute("select count(*) from questions where survey_id = %s", (survey["id"],))
        assert left.fetchone() == (0,)


@pytest.mark.db
@needs_db
def test_actions_on_unknown_survey_are_404(client):
    missing = uuid4()
    for action in ("duplicate", "close", "unpublish"):
        assert client.post(f"/api/v1/surveys/{missing}/{action}").status_code == 404
    assert client.delete(f"/api/v1/surveys/{missing}").status_code == 404


@pytest.mark.db
@needs_db
def test_other_tenant_cannot_act_on_a_survey(client):
    survey = make_survey(client, unique("Members only"), status="live")
    url = f"/api/v1/surveys/{survey['id']}"

    app.dependency_overrides[current_user] = lambda: as_user(OTHER_TENANT)
    assert client.get("/api/v1/surveys", params={"q": survey["title"]}).json() == []
    for action in ("duplicate", "close", "unpublish"):
        assert client.post(f"{url}/{action}").status_code == 404
    assert client.delete(url).status_code == 404

    app.dependency_overrides.clear()
    assert client.get(url).json()["status"] == "live"


# --- Reader options (#44) -----------------------------------------------------


def test_reader_options_must_be_true_or_false(no_db):
    url = f"/api/v1/surveys/{uuid4()}"
    for field in ("comment_field", "show_results", "contact_opt_in"):
        assert no_db.patch(url, json={field: None}).status_code == 422
        assert no_db.patch(url, json={field: "yes"}).status_code == 422
        assert no_db.patch(url, json={field: 1}).status_code == 422


@pytest.mark.db
@needs_db
def test_reader_options_are_on_by_default_and_saved_per_survey(client):
    first = client.post("/api/v1/surveys", json={"type": "nps"}).json()
    second = client.post("/api/v1/surveys", json={"type": "nps"}).json()
    for survey in (first, second):
        assert (survey["comment_field"], survey["show_results"], survey["contact_opt_in"]) == (
            True,
            True,
            True,
        )

    url = f"/api/v1/surveys/{first['id']}"
    r = client.patch(url, json={"show_results": False, "contact_opt_in": False})
    assert r.status_code == 200
    assert (r.json()["comment_field"], r.json()["show_results"], r.json()["contact_opt_in"]) == (
        True,
        False,
        False,
    )
    assert client.get(url).json()["show_results"] is False
    # Other surveys keep their own options.
    assert client.get(f"/api/v1/surveys/{second['id']}").json()["show_results"] is True
    # A copy keeps the options.
    copy = client.post(f"{url}/duplicate").json()
    assert (copy["show_results"], copy["contact_opt_in"]) == (False, False)
