"""Publishing a survey and its links (#5)."""

import os
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from liana_survey_shared import links
from liana_survey_shared.config import get_settings
from liana_survey_shared.db import ping
from liana_survey_shared.web.auth import CurrentUser, current_user
from survey_manager.main import app
from survey_manager.surveys.domain import (
    NotReadyToPublish,
    StatusChangeNotAllowed,
    new_link_token,
    published_status,
)
from survey_manager.surveys.schemas import SurveyStatus as S

needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)
MEMBER_NPS = "00000000-0000-4000-8000-000000000312"


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- Rules ------------------------------------------------------------------------


def test_only_complete_drafts_can_be_published():
    assert published_status(S.draft, "nps", ["nps", "reasons"]) is S.live
    assert published_status(S.draft, "custom", ["text"]) is S.live
    for current in (S.live, S.scheduled, S.closed):
        with pytest.raises(StatusChangeNotAllowed):
            published_status(current, "nps", ["nps"])
    with pytest.raises(NotReadyToPublish, match="Add a question"):
        published_status(S.draft, "custom", [])
    # Template surveys need their main question first.
    with pytest.raises(NotReadyToPublish, match="main question"):
        published_status(S.draft, "csat", ["reasons", "rating"])
    with pytest.raises(NotReadyToPublish, match="main question"):
        published_status(S.draft, "thumbs", ["nps"])


def test_link_tokens_are_long_random_and_url_safe():
    tokens = {new_link_token() for _ in range(200)}
    assert len(tokens) == 200
    for token in tokens:
        assert len(token) == 22
        assert token.replace("-", "").replace("_", "").isalnum()


# --- API --------------------------------------------------------------------------


def from_template(client) -> dict:
    return client.post(f"/api/v1/templates/{MEMBER_NPS}/surveys").json()


@pytest.mark.db
@needs_db
def test_publish_makes_a_draft_live_with_a_public_link(client):
    survey = from_template(client)
    assert (survey["public_url"], survey["published_at"]) == (None, None)

    r = client.post(f"/api/v1/surveys/{survey['id']}/publish")
    assert r.status_code == 200
    published = r.json()
    assert published["status"] == "live"
    assert published["published_at"] is not None
    base = get_settings().public_base_url.rstrip("/")
    assert published["public_url"].startswith(f"{base}/r/")
    assert len(published["public_url"].rsplit("/", 1)[1]) == 22
    assert "link_token" not in published
    assert (
        client.get(f"/api/v1/surveys/{survey['id']}").json()["public_url"]
        == published["public_url"]
    )


@pytest.mark.db
@needs_db
def test_the_public_link_survives_unpublish_and_publish_again(client):
    survey = from_template(client)
    url = f"/api/v1/surveys/{survey['id']}"
    first = client.post(f"{url}/publish").json()["public_url"]
    assert client.post(f"{url}/unpublish").json()["status"] == "draft"
    again = client.post(f"{url}/publish").json()
    assert (again["status"], again["public_url"]) == ("live", first)


@pytest.mark.db
@needs_db
def test_publishing_twice_or_an_incomplete_draft_is_409(client):
    survey = from_template(client)
    url = f"/api/v1/surveys/{survey['id']}"
    client.post(f"{url}/publish")
    r = client.post(f"{url}/publish")
    assert r.status_code == 409
    assert "live" in r.json()["detail"]

    empty = client.post("/api/v1/surveys", json={"type": "custom"}).json()
    r = client.post(f"/api/v1/surveys/{empty['id']}/publish")
    assert (r.status_code, r.json()["detail"]) == (409, "Add a question before publishing.")
    assert client.get(f"/api/v1/surveys/{empty['id']}").json()["status"] == "draft"


@pytest.mark.db
@needs_db
def test_copies_get_their_own_link_when_published(client):
    survey = from_template(client)
    original = client.post(f"/api/v1/surveys/{survey['id']}/publish").json()
    copy = client.post(f"/api/v1/surveys/{survey['id']}/duplicate").json()
    assert (copy["status"], copy["public_url"]) == ("draft", None)
    published_copy = client.post(f"/api/v1/surveys/{copy['id']}/publish").json()
    assert published_copy["public_url"] != original["public_url"]


@pytest.mark.db
@needs_db
def test_unknown_survey_is_404(client):
    assert client.post(f"/api/v1/surveys/{uuid4()}/publish").status_code == 404
    assert client.post(f"/api/v1/surveys/{uuid4()}/test-links").status_code == 404


@pytest.mark.db
@needs_db
def test_test_links_are_signed_per_reader(client):
    survey = from_template(client)
    url = f"/api/v1/surveys/{survey['id']}"
    assert client.post(f"{url}/test-links").status_code == 409  # not published yet

    public = client.post(f"{url}/publish").json()["public_url"]
    r = client.post(f"{url}/test-links", json={"count": 2})
    assert r.status_code == 200
    made = r.json()["links"]
    assert len(made) == 2
    settings = get_settings()
    token = public.rsplit("/", 1)[1]
    refs = []
    for link in made:
        parts = urlsplit(link)
        assert link.startswith(f"{public}?")
        query = parse_qs(parts.query)
        links.check_signature(settings.link_signing_secret, token, query["r"][0], query["s"][0])
        refs.append(query["r"][0])
    assert len(set(refs)) == 2
    assert client.post(f"{url}/test-links", json={"count": 21}).status_code == 422


@pytest.mark.db
@needs_db
def test_test_links_exist_only_in_local_development(client, monkeypatch):
    survey = from_template(client)
    client.post(f"/api/v1/surveys/{survey['id']}/publish")
    signed_in = get_settings().model_copy()
    monkeypatch.setattr(get_settings(), "auth_mode", "liana")
    # A signed-in user outside dev mode still gets no test links.
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        user_id=signed_in.dev_user_id,
        tenant_id=signed_in.dev_tenant_id,
        tenant_name=signed_in.dev_tenant_name,
        name=signed_in.dev_user_name,
        email=signed_in.dev_user_email,
    )
    assert client.post(f"/api/v1/surveys/{survey['id']}/test-links").status_code == 404
