"""Tests for question editing under /api/v1/surveys/{id}/questions."""

import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from liana_survey_shared.db import ping
from liana_survey_shared.web.auth import CurrentUser, current_user
from liana_survey_shared.web.db import tenant_db
from survey_manager.main import app

OTHER_TENANT = UUID("00000000-0000-4000-8000-0000000000ff")
needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def no_db(client):
    app.dependency_overrides[tenant_db] = lambda: None
    return client


def as_user(tenant_id: UUID) -> CurrentUser:
    return CurrentUser(
        user_id=uuid4(),
        tenant_id=tenant_id,
        tenant_name="Test tenant",
        name="Test user",
        email="test@example.org",
    )


def new_survey(client: TestClient) -> str:
    response = client.post("/api/v1/surveys", json={"type": "custom"})
    assert response.status_code == 201
    return response.json()["id"]


def add_question(client: TestClient, survey_id: str, prompt: str, **changes) -> dict:
    body = {"kind": "text", "prompt": prompt, **changes}
    response = client.post(f"/api/v1/surveys/{survey_id}/questions", json=body)
    assert response.status_code == 201
    return response.json()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"kind": "paragraph"},
        {"kind": "text", "position": 1},
        {"kind": "text", "required": None},
        {"kind": "text", "options": [{"label": "invalid"}]},
    ],
)
def test_add_rejects_invalid_body(no_db, body):
    assert no_db.post(f"/api/v1/surveys/{uuid4()}/questions", json=body).status_code == 422


def test_edit_rejects_null_and_server_fields(no_db):
    url = f"/api/v1/surveys/{uuid4()}/questions/{uuid4()}"
    for body in (
        {"prompt": None},
        {"kind": None},
        {"options": None},
        {"required": None},
        {"position": 2},
    ):
        assert no_db.patch(url, json=body).status_code == 422


def test_order_rejects_duplicate_ids_without_a_database(no_db):
    question_id = str(uuid4())
    response = no_db.put(
        f"/api/v1/surveys/{uuid4()}/questions/order",
        json={"question_ids": [question_id, question_id]},
    )
    assert response.status_code == 422


@pytest.mark.db
@needs_db
def test_add_list_edit_and_delete_questions(client):
    survey_id = new_survey(client)
    first = add_question(
        client,
        survey_id,
        "Pick any that apply",
        kind="multiple_choice",
        options=["Events", "Newsletter"],
        required=False,
    )
    second = add_question(client, survey_id, "Tell us more")

    assert first["position"] == 1
    assert first["required"] is False
    assert first["options"] == ["Events", "Newsletter"]
    assert second["position"] == 2
    listed = client.get(f"/api/v1/surveys/{survey_id}/questions")
    assert listed.status_code == 200
    assert [question["id"] for question in listed.json()] == [first["id"], second["id"]]

    edited = client.patch(
        f"/api/v1/surveys/{survey_id}/questions/{first['id']}",
        json={"prompt": "Choose all that apply", "required": True},
    )
    assert edited.status_code == 200
    assert edited.json()["prompt"] == "Choose all that apply"
    assert edited.json()["required"] is True
    assert edited.json()["kind"] == "multiple_choice"

    deleted = client.delete(f"/api/v1/surveys/{survey_id}/questions/{first['id']}")
    assert deleted.status_code == 204
    remaining = client.get(f"/api/v1/surveys/{survey_id}/questions").json()
    assert [(question["id"], question["position"]) for question in remaining] == [(second["id"], 1)]


@pytest.mark.db
@needs_db
def test_duplicate_is_inserted_after_the_source_and_order_can_be_changed(client):
    survey_id = new_survey(client)
    first = add_question(
        client,
        survey_id,
        "First",
        kind="single_choice",
        options=["Yes", "No"],
        required=False,
    )
    second = add_question(client, survey_id, "Second", kind="rating", options=[1, 2, 3, 4, 5])

    duplicated = client.post(f"/api/v1/surveys/{survey_id}/questions/{first['id']}/duplicate")
    assert duplicated.status_code == 201
    copy = duplicated.json()
    assert copy["id"] != first["id"]
    assert copy["prompt"] == first["prompt"]
    assert copy["options"] == first["options"]
    assert copy["required"] == first["required"]
    assert copy["position"] == 2

    before = client.get(f"/api/v1/surveys/{survey_id}/questions").json()
    assert [question["id"] for question in before] == [first["id"], copy["id"], second["id"]]
    order = [second["id"], copy["id"], first["id"]]
    reordered = client.put(
        f"/api/v1/surveys/{survey_id}/questions/order", json={"question_ids": order}
    )
    assert reordered.status_code == 200
    assert [question["id"] for question in reordered.json()] == order
    assert [question["position"] for question in reordered.json()] == [1, 2, 3]
    assert [
        question["id"] for question in client.get(f"/api/v1/surveys/{survey_id}/questions").json()
    ] == order


@pytest.mark.db
@needs_db
def test_reorder_requires_every_question_exactly_once(client):
    survey_id = new_survey(client)
    first = add_question(client, survey_id, "First")
    second = add_question(client, survey_id, "Second")

    response = client.put(
        f"/api/v1/surveys/{survey_id}/questions/order",
        json={"question_ids": [second["id"]]},
    )
    assert response.status_code == 422
    assert "every question" in response.json()["detail"]
    current = client.get(f"/api/v1/surveys/{survey_id}/questions").json()
    assert [question["id"] for question in current] == [first["id"], second["id"]]


@pytest.mark.db
@needs_db
def test_unknown_survey_and_question_are_404(client):
    missing_survey = uuid4()
    assert client.get(f"/api/v1/surveys/{missing_survey}/questions").status_code == 404

    survey_id = new_survey(client)
    missing_question = uuid4()
    base = f"/api/v1/surveys/{survey_id}/questions/{missing_question}"
    assert client.patch(base, json={"prompt": "Missing"}).status_code == 404
    assert client.delete(base).status_code == 404
    assert client.post(f"{base}/duplicate").status_code == 404


@pytest.mark.db
@needs_db
def test_other_tenant_cannot_access_questions(client):
    survey_id = new_survey(client)
    question = add_question(client, survey_id, "Tenant secret")
    app.dependency_overrides[current_user] = lambda: as_user(OTHER_TENANT)

    assert client.get(f"/api/v1/surveys/{survey_id}/questions").status_code == 404
    assert (
        client.patch(
            f"/api/v1/surveys/{survey_id}/questions/{question['id']}",
            json={"prompt": "Hijacked"},
        ).status_code
        == 404
    )

    app.dependency_overrides.clear()
    saved = client.get(f"/api/v1/surveys/{survey_id}/questions").json()
    assert saved[0]["prompt"] == "Tenant secret"
