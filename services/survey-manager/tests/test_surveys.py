"""Tests for /api/v1/surveys.

Validation tests run anywhere. Tests marked `db` need a migrated Postgres
reached as the app role (so row-level security applies), e.g. in CI's db job:

    DATABASE_URL=postgresql://survey_app:...@localhost:5432/survey pytest -m db

They are skipped when no database answers, unless REQUIRE_DB=1 (set in CI),
so CI can never pass by silently skipping them.
"""

import os
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
        {"type": "nps", "title": "x" * 201},  # too long
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


def test_bad_survey_id_is_422(no_db):
    assert no_db.get("/api/v1/surveys/not-a-uuid").status_code == 422


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
    created = client.post("/api/v1/surveys", json={"type": "csat", "title": "Reopen me"}).json()

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
