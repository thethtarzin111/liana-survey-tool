"""Tests for /api/v1/contact-requests (#56): readers who ticked "Contact me",
filtered by status, with status updates as the team replies."""

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from liana_survey_shared.db import ping, tenant_connection
from liana_survey_shared.web.auth import CurrentUser, current_user
from liana_survey_shared.web.db import tenant_db
from survey_manager.contact_requests.domain import counts
from survey_manager.main import app

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")
OTHER_TENANT = UUID("00000000-0000-4000-8000-0000000000ff")

needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)


@pytest.fixture
def client():
    # The dev-auth demo user (Anna Virtanen, Example Members Association).
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_counts_have_every_status_and_a_total():
    assert counts([("done", 2), ("new", 3)]) == {"all": 5, "new": 3, "contacted": 0, "done": 2}
    assert counts([]) == {"all": 0, "new": 0, "contacted": 0, "done": 0}


def test_bad_filters_and_statuses_are_422(client):
    app.dependency_overrides[tenant_db] = lambda: None
    assert client.get("/api/v1/contact-requests?status=resolved").status_code == 422
    assert client.get("/api/v1/contact-requests?survey_id=nope").status_code == 422
    assert (
        client.patch(f"/api/v1/contact-requests/{uuid4()}", json={"status": "x"}).status_code == 422
    )


# --- With a database --------------------------------------------------------------


@pytest.fixture
def make_request():
    """Creates a survey with an NPS and a reasons question, and contact requests
    for readers of it. Deletes the surveys afterwards."""
    surveys: dict[str, tuple[UUID, UUID, UUID]] = {}

    def create(
        title="Contact test",
        *,
        score=3,
        reasons=("Price", "Service"),
        status="new",
        ref="member-1042",
        minutes_ago=0,
    ) -> UUID:
        with tenant_connection(DEMO_TENANT) as conn:
            if title not in surveys:
                survey_id = conn.execute(
                    """insert into surveys (tenant_id, title, type)
                       values (%s, %s, 'nps') returning id""",
                    (DEMO_TENANT, title),
                ).fetchone()[0]
                main = conn.execute(
                    """insert into questions (tenant_id, survey_id, position, kind, prompt)
                       values (%s, %s, 1, 'nps', 'Recommend?') returning id""",
                    (DEMO_TENANT, survey_id),
                ).fetchone()[0]
                why = conn.execute(
                    """insert into questions
                         (tenant_id, survey_id, position, kind, prompt, options, required)
                       values (%s, %s, 2, 'reasons', '', '["Price","Service"]', false)
                       returning id""",
                    (DEMO_TENANT, survey_id),
                ).fetchone()[0]
                surveys[title] = (survey_id, main, why)
            survey_id, main, why = surveys[title]
            response_id = conn.execute(
                """insert into responses (tenant_id, survey_id, link_token_hash, contact_ref,
                                          segment)
                   values (%s, %s, %s, %s, 'members') returning id""",
                (DEMO_TENANT, survey_id, f"key-{uuid4()}", ref),
            ).fetchone()[0]
            conn.execute(
                """insert into answers (tenant_id, response_id, question_id, value_number)
                   values (%s, %s, %s, %s)""",
                (DEMO_TENANT, response_id, main, score),
            )
            if reasons:
                conn.execute(
                    """insert into answers (tenant_id, response_id, question_id, value_choices)
                       values (%s, %s, %s, %s)""",
                    (DEMO_TENANT, response_id, why, Jsonb(list(reasons))),
                )
            return conn.execute(
                """insert into contact_requests
                     (tenant_id, survey_id, response_id, contact_ref, status, created_at)
                   values (%s, %s, %s, %s, %s, %s) returning id""",
                (
                    DEMO_TENANT,
                    survey_id,
                    response_id,
                    ref,
                    status,
                    datetime.now(UTC) - timedelta(minutes=minutes_ago),
                ),
            ).fetchone()[0]

    create.survey_id = lambda title="Contact test": surveys[title][0]
    yield create
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("delete from surveys where id = any(%s)", ([s[0] for s in surveys.values()],))


def listed(client, **params):
    response = client.get("/api/v1/contact-requests", params=params)
    assert response.status_code == 200
    return response.json()


@pytest.mark.db
@needs_db
def test_a_request_shows_the_reader_by_contact_reference_with_their_answer(client, make_request):
    request_id = make_request(score=3, reasons=("Price", "Service"))
    page = listed(client, survey_id=str(make_request.survey_id()))
    [item] = page["items"]
    assert item["id"] == str(request_id)
    assert item["contact_ref"] == "member-1042"
    assert (item["survey_title"], item["survey_type"]) == ("Contact test", "nps")
    assert (item["answer"], item["reason"], item["segment"]) == (3, "Price; Service", "members")
    assert (item["status"], item["liana_status"]) == ("new", "pending")
    # Never an e-mail address: the reader is only known by the contact reference.
    assert not any("mail" in key for key in item)


@pytest.mark.db
@needs_db
def test_requests_are_newest_first_and_filter_by_status(client, make_request):
    old = make_request(status="done", minutes_ago=30)
    new = make_request(status="new", minutes_ago=1)
    contacted = make_request(status="contacted", minutes_ago=10)
    survey = str(make_request.survey_id())
    page = listed(client, survey_id=survey)
    assert [i["id"] for i in page["items"]] == [str(new), str(contacted), str(old)]
    assert page["counts"] == {"all": 3, "new": 1, "contacted": 1, "done": 1}
    done = listed(client, survey_id=survey, status="done")
    assert [i["id"] for i in done["items"]] == [str(old)]
    # The chips keep showing every status while one is picked.
    assert done["counts"]["all"] == 3


@pytest.mark.db
@needs_db
def test_requests_filter_by_survey(client, make_request):
    make_request("Survey A")
    make_request("Survey B")
    page = listed(client, survey_id=str(make_request.survey_id("Survey B")))
    assert [i["survey_title"] for i in page["items"]] == ["Survey B"]
    assert page["counts"]["all"] == 1


@pytest.mark.db
@needs_db
def test_a_request_without_reasons_has_no_reason(client, make_request):
    make_request(reasons=())
    [item] = listed(client, survey_id=str(make_request.survey_id()))["items"]
    assert item["reason"] is None


@pytest.mark.db
@needs_db
def test_the_status_is_updated_as_the_team_replies(client, make_request):
    request_id = make_request()
    response = client.patch(f"/api/v1/contact-requests/{request_id}", json={"status": "contacted"})
    assert response.status_code == 200
    assert response.json()["status"] == "contacted"
    [item] = listed(client, survey_id=str(make_request.survey_id()), status="contacted")["items"]
    assert item["id"] == str(request_id)


@pytest.mark.db
@needs_db
def test_unknown_requests_are_404(client):
    response = client.patch(f"/api/v1/contact-requests/{uuid4()}", json={"status": "done"})
    assert response.status_code == 404


@pytest.mark.db
@needs_db
def test_another_organisation_cannot_see_or_change_requests(client, make_request):
    request_id = make_request()
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        user_id=uuid4(),
        tenant_id=OTHER_TENANT,
        tenant_name="Other",
        name="Other user",
        email="other@example.org",
    )
    assert listed(client)["items"] == []
    response = client.patch(f"/api/v1/contact-requests/{request_id}", json={"status": "done"})
    assert response.status_code == 404
