"""Tests for /api/v1/templates and the survey thank-you message (#36).

Template data comes from migration 20261117090000_templates_and_thank_you.sql.
"""

import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from liana_survey_shared.db import ping
from liana_survey_shared.web.auth import CurrentUser, current_user
from liana_survey_shared.web.db import tenant_db
from survey_manager.main import app
from survey_manager.templates.domain import personalise

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")
OTHER_TENANT = UUID("00000000-0000-4000-8000-0000000000ff")
MEMBER_NPS = "00000000-0000-4000-8000-000000000312"
NEWSLETTER = "00000000-0000-4000-8000-000000000311"
QUICK_POLL = "00000000-0000-4000-8000-000000000315"

needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)


def as_user(tenant_id: UUID, tenant_name: str = "Test tenant") -> CurrentUser:
    return CurrentUser(
        user_id=uuid4(),
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        name="Test user",
        email="test@example.org",
    )


@pytest.fixture
def client():
    # The dev-auth demo user (Anna Virtanen, Example Members Association).
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_organisation_name_is_filled_in():
    assert personalise("Recommend {organisation}?", "Example Members Association") == (
        "Recommend Example Members Association?"
    )
    assert personalise("No placeholder", "X") == "No placeholder"


def test_bad_ids_and_types_are_422(client):
    app.dependency_overrides[tenant_db] = lambda: None
    assert client.get("/api/v1/templates?type=poll").status_code == 422
    assert client.post("/api/v1/templates/not-a-uuid/surveys").status_code == 422


@pytest.mark.db
@needs_db
def test_lists_built_in_templates_in_order_with_the_organisation_name(client):
    templates = client.get("/api/v1/templates").json()
    built_in = [t for t in templates if t["id"].startswith("00000000-0000-4000-8000-0000000003")]
    assert [t["name"] for t in built_in] == [
        "Newsletter feedback",
        "Member NPS",
        "Event feedback",
        "Course satisfaction",
        "Quick poll",
        "Course feedback",
        "Employee NPS (eNPS)",
        "Event satisfaction",
    ]
    assert [t["featured"] for t in built_in] == [True] * 5 + [False] * 3

    member_nps = next(t for t in built_in if t["id"] == MEMBER_NPS)
    assert member_nps["type"] == "nps"
    assert member_nps["thank_you"] == "Thank you. This takes our member work forward."
    assert member_nps["questions"][0] == {
        "kind": "nps",
        "prompt": (
            "How likely are you to recommend Example Members Association to a friend or colleague?"
        ),
        "options": [],
        "required": True,
    }
    assert member_nps["questions"][1]["kind"] == "reasons"
    assert member_nps["questions"][1]["required"] is False


@pytest.mark.db
@needs_db
def test_filters_templates_by_survey_type(client):
    nps = client.get("/api/v1/templates", params={"type": "nps"}).json()
    assert {t["type"] for t in nps} == {"nps"}
    assert [t["name"] for t in nps][:2] == ["Member NPS", "Employee NPS (eNPS)"]


@pytest.mark.db
@needs_db
def test_using_a_template_creates_a_draft_with_its_questions(client):
    r = client.post(f"/api/v1/templates/{MEMBER_NPS}/surveys")
    assert r.status_code == 201
    survey = r.json()
    assert survey["title"] == "Member NPS"
    assert survey["type"] == "nps"
    assert survey["status"] == "draft"
    assert survey["thank_you"] == "Thank you. This takes our member work forward."

    questions = client.get(f"/api/v1/surveys/{survey['id']}/questions").json()
    assert [(q["position"], q["kind"], q["required"]) for q in questions] == [
        (1, "nps", True),
        (2, "reasons", False),
    ]
    assert "Example Members Association" in questions[0]["prompt"]
    assert questions[1]["options"] == [
        "Events and activities",
        "Hard to find information",
        "Membership fee",
        "Something else",
    ]


@pytest.mark.db
@needs_db
def test_every_built_in_template_can_be_used(client):
    for template in client.get("/api/v1/templates").json():
        r = client.post(f"/api/v1/templates/{template['id']}/surveys")
        assert r.status_code == 201, template["name"]
        questions = client.get(f"/api/v1/surveys/{r.json()['id']}/questions").json()
        assert [q["kind"] for q in questions] == [q["kind"] for q in template["questions"]]


@pytest.mark.db
@needs_db
def test_thumbs_and_quick_poll_templates(client):
    thumbs = client.post(f"/api/v1/templates/{NEWSLETTER}/surveys").json()
    first = client.get(f"/api/v1/surveys/{thumbs['id']}/questions").json()[0]
    assert (first["kind"], first["prompt"], first["options"]) == (
        "thumbs",
        "How was this newsletter?",
        [],
    )

    poll = client.post(f"/api/v1/templates/{QUICK_POLL}/surveys").json()
    assert poll["type"] == "custom"
    assert poll["thank_you"] is None  # Quick poll has no thank-you message


@pytest.mark.db
@needs_db
def test_unknown_template_is_404(client):
    assert client.post(f"/api/v1/templates/{uuid4()}/surveys").status_code == 404


@pytest.mark.db
@needs_db
def test_organisations_see_only_built_in_and_their_own_templates(client):
    from liana_survey_shared.db import tenant_connection

    own_id = uuid4()
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute(
            """insert into templates (id, tenant_id, name, type, questions)
               values (%s, %s, 'Demo org only', 'custom',
                       '[{"kind":"text","prompt":"Hi?"}]')""",
            (own_id, DEMO_TENANT),
        )
    try:
        # The demo organisation sees and can use its own template...
        assert str(own_id) in [t["id"] for t in client.get("/api/v1/templates").json()]
        assert client.post(f"/api/v1/templates/{own_id}/surveys").status_code == 201

        # ...another organisation sees only the built-in ones.
        app.dependency_overrides[current_user] = lambda: as_user(OTHER_TENANT)
        ids = [t["id"] for t in client.get("/api/v1/templates").json()]
        assert str(own_id) not in ids and MEMBER_NPS in ids
        assert client.post(f"/api/v1/templates/{own_id}/surveys").status_code == 404
    finally:
        with tenant_connection(DEMO_TENANT) as conn:
            conn.execute("delete from templates where id = %s", (own_id,))


# --- Thank-you message on surveys ---------------------------------------------


@pytest.mark.db
@needs_db
def test_thank_you_message_can_be_set_cleared_and_is_copied(client):
    survey = client.post(f"/api/v1/templates/{NEWSLETTER}/surveys").json()
    url = f"/api/v1/surveys/{survey['id']}"

    r = client.patch(url, json={"thank_you": "  Thanks a lot!  "})
    assert (r.status_code, r.json()["thank_you"]) == (200, "Thanks a lot!")
    copy = client.post(f"{url}/duplicate").json()
    assert copy["thank_you"] == "Thanks a lot!"

    assert client.patch(url, json={"thank_you": ""}).json()["thank_you"] is None
    assert client.patch(url, json={"thank_you": "x" * 501}).status_code == 422
    assert client.patch(url, json={"thank_you": None}).status_code == 422
