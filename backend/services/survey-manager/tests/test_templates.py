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
from survey_manager.templates.domain import NoQuestions, personalise, saved_questions

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
    # Built-in templates have no colours: the survey gets the defaults.
    assert (survey["accent_color"], survey["background_color"]) == ("#0F6A5E", "#FFFFFF")

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


# --- The organisation's own templates -------------------------------------------


def test_saved_questions_keep_their_order_and_need_one():
    rows = [
        {"id": 1, "position": 1, "kind": "nps", "prompt": "Recommend?", "options": [],
         "required": True},
        {"id": 2, "position": 2, "kind": "reasons", "prompt": "", "options": ["Price"],
         "required": False},
    ]  # fmt: skip
    assert saved_questions(rows) == [
        {"kind": "nps", "prompt": "Recommend?", "options": [], "required": True},
        {"kind": "reasons", "prompt": "", "options": ["Price"], "required": False},
    ]
    with pytest.raises(NoQuestions):
        saved_questions([])


def test_bad_template_bodies_are_422(client):
    app.dependency_overrides[tenant_db] = lambda: None
    survey_id = str(uuid4())
    assert client.post("/api/v1/templates", json={"survey_id": survey_id}).status_code == 422
    for body in (
        {"survey_id": survey_id, "name": "   "},
        {"survey_id": survey_id, "name": "x" * 81},
        {"survey_id": "not-a-uuid", "name": "Mine"},
        {"survey_id": survey_id, "name": "Mine", "featured": True},
    ):
        assert client.post("/api/v1/templates", json=body).status_code == 422, body
    url = f"/api/v1/templates/{uuid4()}"
    assert client.patch(url, json={"name": None}).status_code == 422
    assert client.patch(url, json={"type": "nps"}).status_code == 422
    assert client.delete("/api/v1/templates/not-a-uuid").status_code == 422


def _save(client, survey_id: str, name: str = "Our member NPS", **extra) -> dict:
    r = client.post("/api/v1/templates", json={"survey_id": survey_id, "name": name, **extra})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.db
@needs_db
def test_save_a_survey_as_a_template_and_use_it(client):
    survey = client.post(f"/api/v1/templates/{MEMBER_NPS}/surveys").json()
    url = f"/api/v1/surveys/{survey['id']}"
    colours = {"accent_color": "#7A2E6E", "background_color": "#FAF6EE"}
    client.patch(url, json={"thank_you": "Thanks, team!", **colours})
    reasons = client.get(f"{url}/questions").json()[1]
    client.patch(f"{url}/questions/{reasons['id']}", json={"options": ["Price", "Events"]})

    template = _save(client, survey["id"], description="  For the yearly check  ")
    try:
        assert template["name"] == "Our member NPS"
        assert template["description"] == "For the yearly check"
        assert (template["type"], template["thank_you"]) == ("nps", "Thanks, team!")
        assert (template["own"], template["featured"]) == (True, False)
        assert (template["accent_color"], template["background_color"]) == ("#7A2E6E", "#FAF6EE")
        assert [(q["kind"], q["options"]) for q in template["questions"]] == [
            ("nps", []),
            ("reasons", ["Price", "Events"]),
        ]

        # Listed after the built-in ones, which stay read-only.
        listed = client.get("/api/v1/templates", params={"type": "nps"}).json()
        assert [t["name"] for t in listed] == [
            "Member NPS",
            "Employee NPS (eNPS)",
            "Our member NPS",
        ]
        assert [t["own"] for t in listed] == [False, False, True]

        copy = client.post(f"/api/v1/templates/{template['id']}/surveys").json()
        assert (copy["title"], copy["thank_you"]) == ("Our member NPS", "Thanks, team!")
        # The branding colours carry over to surveys made from the template.
        assert (copy["accent_color"], copy["background_color"]) == ("#7A2E6E", "#FAF6EE")
        questions = client.get(f"/api/v1/surveys/{copy['id']}/questions").json()
        assert [q["options"] for q in questions] == [[], ["Price", "Events"]]
    finally:
        client.delete(f"/api/v1/templates/{template['id']}")


@pytest.mark.db
@needs_db
def test_rename_and_delete_your_own_template(client):
    survey = client.post(f"/api/v1/templates/{QUICK_POLL}/surveys").json()
    template = _save(client, survey["id"], name="Poll")
    url = f"/api/v1/templates/{template['id']}"

    r = client.patch(url, json={"name": " Board poll "})
    assert (r.status_code, r.json()["name"], r.json()["description"]) == (200, "Board poll", "")
    r = client.patch(url, json={"description": "Two options"})
    assert (r.json()["name"], r.json()["description"]) == ("Board poll", "Two options")
    assert client.patch(url, json={}).json()["name"] == "Board poll"

    assert client.delete(url).status_code == 204
    assert template["id"] not in [t["id"] for t in client.get("/api/v1/templates").json()]
    assert client.delete(url).status_code == 404
    assert client.patch(url, json={"name": "Gone"}).status_code == 404
    # Surveys made from a template stay when it is deleted.
    assert client.get(f"/api/v1/surveys/{survey['id']}").status_code == 200


@pytest.mark.db
@needs_db
def test_built_in_templates_are_read_only(client):
    url = f"/api/v1/templates/{MEMBER_NPS}"
    r = client.patch(url, json={"name": "Mine now"})
    assert (r.status_code, r.json()["detail"]) == (403, "Built-in templates cannot be changed.")
    assert client.delete(url).status_code == 403
    member_nps = next(t for t in client.get("/api/v1/templates").json() if t["id"] == MEMBER_NPS)
    assert (member_nps["name"], member_nps["own"]) == ("Member NPS", False)


@pytest.mark.db
@needs_db
def test_a_survey_without_questions_or_from_elsewhere_cannot_be_saved(client):
    empty = client.post("/api/v1/surveys", json={"type": "custom"}).json()
    r = client.post("/api/v1/templates", json={"survey_id": empty["id"], "name": "Empty"})
    assert (r.status_code, r.json()["detail"]) == (
        409,
        "Add a question before you save the survey as a template.",
    )
    r = client.post("/api/v1/templates", json={"survey_id": str(uuid4()), "name": "Nope"})
    assert (r.status_code, r.json()["detail"]) == (404, "Survey not found")

    # Another organisation cannot save the demo organisation's survey either.
    survey = client.post(f"/api/v1/templates/{NEWSLETTER}/surveys").json()
    app.dependency_overrides[current_user] = lambda: as_user(OTHER_TENANT)
    r = client.post("/api/v1/templates", json={"survey_id": survey["id"], "name": "Theirs"})
    assert r.status_code == 404


@pytest.mark.db
@needs_db
def test_other_organisations_cannot_rename_or_delete_your_template(client):
    survey = client.post(f"/api/v1/templates/{NEWSLETTER}/surveys").json()
    template = _save(client, survey["id"], name="Our newsletter")
    url = f"/api/v1/templates/{template['id']}"
    try:
        app.dependency_overrides[current_user] = lambda: as_user(OTHER_TENANT)
        assert client.patch(url, json={"name": "Taken"}).status_code == 404
        assert client.delete(url).status_code == 404
        assert template["id"] not in [t["id"] for t in client.get("/api/v1/templates").json()]
    finally:
        app.dependency_overrides.clear()
        assert client.get("/api/v1/templates").status_code == 200
        names = {t["id"]: t["name"] for t in client.get("/api/v1/templates").json()}
        assert names[template["id"]] == "Our newsletter"
        client.delete(url)


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
