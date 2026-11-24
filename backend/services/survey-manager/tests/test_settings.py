"""Survey settings (#47): close date, response limit and "notify me"."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from liana_survey_shared.db import ping
from liana_survey_shared.web.db import tenant_db
from survey_manager.main import app
from survey_manager.surveys.domain import BadSettings, check_close_date

needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- Rules ----------------------------------------------------------------------


def test_a_close_date_must_be_in_the_future():
    check_close_date(NOW + timedelta(minutes=1), NOW)
    check_close_date(None, NOW)
    for past in (NOW, NOW - timedelta(days=1)):
        with pytest.raises(BadSettings, match="in the future"):
            check_close_date(past, NOW)


# --- API without a database ---------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"response_limit": 0},
        {"response_limit": -5},
        {"response_limit": 1_000_001},
        {"response_limit": "100"},
        {"response_limit": 10.5},
        {"notify_on_response": "yes"},
        {"notify_on_response": None},
        # Without a time zone the moment is unclear.
        {"closes_at": "2099-01-01T00:00:00"},
        {"closes_at": "2000-01-01T00:00:00Z"},
        {"closes_at": "soon"},
    ],
)
def test_bad_settings_are_refused_before_saving(client, body):
    app.dependency_overrides[tenant_db] = lambda: None
    assert client.patch(f"/api/v1/surveys/{uuid4()}", json=body).status_code == 422


def test_a_past_close_date_says_why(client):
    app.dependency_overrides[tenant_db] = lambda: None
    r = client.patch(f"/api/v1/surveys/{uuid4()}", json={"closes_at": "2000-01-01T00:00:00Z"})
    assert r.json()["detail"] == "The close date must be in the future."


# --- With a database ------------------------------------------------------------


@pytest.mark.db
@needs_db
def test_settings_are_saved_cleared_and_copied(client):
    survey = client.post("/api/v1/surveys", json={"type": "nps", "title": "Settings test"}).json()
    url = f"/api/v1/surveys/{survey['id']}"
    try:
        assert (survey["closes_at"], survey["response_limit"], survey["notify_on_response"]) == (
            None,
            None,
            False,
        )
        r = client.patch(
            url,
            json={
                "closes_at": "2099-12-31T21:59:00+00:00",
                "response_limit": 500,
                "notify_on_response": True,
            },
        )
        assert r.status_code == 200
        saved = client.get(url).json()
        assert datetime.fromisoformat(saved["closes_at"]) == datetime(
            2099, 12, 31, 21, 59, tzinfo=UTC
        )
        assert (saved["response_limit"], saved["notify_on_response"]) == (500, True)

        # Other changes leave the settings alone.
        assert client.patch(url, json={"title": "Renamed"}).json()["response_limit"] == 500

        # A copy keeps the limit and "notify me", but not the dates.
        copy = client.post(f"{url}/duplicate").json()
        assert (copy["closes_at"], copy["response_limit"], copy["notify_on_response"]) == (
            None,
            500,
            True,
        )
        client.delete(f"/api/v1/surveys/{copy['id']}")

        # null removes the close date and the limit.
        r = client.patch(url, json={"closes_at": None, "response_limit": None})
        assert (r.json()["closes_at"], r.json()["response_limit"]) == (None, None)
        assert r.json()["notify_on_response"] is True
    finally:
        client.delete(url)


@pytest.mark.parametrize("body", [{"anonymous": "no"}, {"anonymous": None}, {"anonymous": 0}])
def test_the_identified_answers_setting_takes_only_true_or_false(client, body):
    app.dependency_overrides[tenant_db] = lambda: None
    assert client.patch(f"/api/v1/surveys/{uuid4()}", json=body).status_code == 422


@pytest.mark.db
@needs_db
def test_a_survey_can_be_set_to_identified_answers(client):
    survey = client.post("/api/v1/surveys", json={"type": "nps", "title": "Identified test"}).json()
    url = f"/api/v1/surveys/{survey['id']}"
    try:
        assert survey["anonymous"] is True  # anonymous by default
        assert client.patch(url, json={"anonymous": False}).json()["anonymous"] is False
        assert client.get(url).json()["anonymous"] is False
    finally:
        client.delete(url)
