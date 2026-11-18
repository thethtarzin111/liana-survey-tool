"""Survey language: English, Finnish or Swedish for the fixed texts readers see."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from liana_survey_shared.db import ping
from liana_survey_shared.web.db import tenant_db
from survey_manager.main import app

needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("language", ["de", "EN", "finnish", "", None, 1])
def test_other_languages_are_refused_before_saving(client, language):
    app.dependency_overrides[tenant_db] = lambda: None
    r = client.patch(f"/api/v1/surveys/{uuid4()}", json={"language": language})
    assert r.status_code == 422


@pytest.mark.db
@needs_db
def test_the_language_is_saved_and_copied(client):
    survey = client.post("/api/v1/surveys", json={"type": "nps", "title": "Language test"}).json()
    url = f"/api/v1/surveys/{survey['id']}"
    try:
        assert survey["language"] == "en"
        for language in ("fi", "sv", "en", "fi"):
            assert client.patch(url, json={"language": language}).json()["language"] == language
        assert client.get(url).json()["language"] == "fi"

        # Other changes leave it alone, and a copy keeps it.
        assert client.patch(url, json={"title": "Kieli"}).json()["language"] == "fi"
        copy = client.post(f"{url}/duplicate").json()
        assert copy["language"] == "fi"
        client.delete(f"/api/v1/surveys/{copy['id']}")
    finally:
        client.delete(url)
