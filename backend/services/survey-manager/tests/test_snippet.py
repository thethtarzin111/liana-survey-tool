"""The LianaMailer newsletter snippet (#40)."""

import os
import re
from html import unescape
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from liana_survey_shared.config import get_settings
from liana_survey_shared.db import ping
from survey_manager.main import app
from survey_manager.surveys.domain import NoSnippet, campaign_tag, snippet_html
from survey_manager.surveys.schemas import SurveyStatus as S

needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)
MEMBER_NPS = "00000000-0000-4000-8000-000000000312"
LINK = "https://survey.example.eu/r/tok?r=$id$&c=member-nps&seg=members"


def hrefs(html: str) -> list[str]:
    return [unescape(h) for h in re.findall(r'href="([^"]+)"', html)]


# --- Rules ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("survey_type", "answers", "labels"),
    [
        ("nps", list(range(11)), [str(n) for n in range(11)]),
        ("thumbs", [0, 1, 2], ["Not for me", "Good", "Loved it"]),
        ("csat", [1, 2, 3, 4, 5], ["1", "2", "3", "4", "5"]),
    ],
)
def test_one_link_per_answer(survey_type, answers, labels):
    html = snippet_html(survey_type, S.live, "How likely?", LINK)
    assert hrefs(html) == [f"{LINK}&a={a}" for a in answers]
    assert re.findall(r">([^<>]+)</a>", html) == labels
    # Email clients: plain tables and inline styles, no scripts or style blocks.
    assert html.startswith('<table role="presentation"')
    assert "<script" not in html and "<style" not in html and "class=" not in html


def test_the_question_is_escaped():
    html = snippet_html("nps", S.live, 'Is "A & B" <good>?', LINK)
    assert "Is &quot;A &amp; B&quot; &lt;good&gt;?" in html
    assert "<good>" not in html


def test_only_live_template_surveys_with_a_question_have_a_snippet():
    for status in (S.draft, S.scheduled, S.closed):
        with pytest.raises(NoSnippet, match="Publish"):
            snippet_html("nps", status, "How likely?", LINK)
    with pytest.raises(NoSnippet, match="Custom surveys"):
        snippet_html("custom", S.live, "Which?", LINK)
    with pytest.raises(NoSnippet, match="main question"):
        snippet_html("nps", S.live, None, LINK)


def test_campaign_tags_are_slugs_of_the_survey_name():
    assert campaign_tag("Member NPS 2026") == "member-nps-2026"
    assert campaign_tag("  Kesä/Summer -- feedback! ") == "kes-summer-feedback"
    assert campaign_tag("???") == "campaign"
    assert len(campaign_tag("x" * 80)) == 40


# --- API --------------------------------------------------------------------------


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def published(client) -> dict:
    survey = client.post(f"/api/v1/templates/{MEMBER_NPS}/surveys").json()
    return client.post(f"/api/v1/surveys/{survey['id']}/publish").json()


@pytest.mark.db
@needs_db
def test_the_snippet_links_carry_the_reader_placeholder_and_tags(client):
    survey = published(client)
    r = client.get(
        f"/api/v1/surveys/{survey['id']}/snippet",
        params={"campaign": "spring-24", "segment": "members"},
    )
    assert r.status_code == 200
    body = r.json()
    assert (body["campaign"], body["segment"]) == ("spring-24", "members")
    tag = get_settings().mailer_reader_tag
    first = hrefs(body["html"])[0]
    assert first == f"{survey['public_url']}?r={tag}&c=spring-24&seg=members&a=0"


@pytest.mark.db
@needs_db
def test_tags_default_to_the_survey_name_and_all(client):
    survey = published(client)
    body = client.get(f"/api/v1/surveys/{survey['id']}/snippet").json()
    assert (body["campaign"], body["segment"]) == (campaign_tag(survey["title"]), "all")


@pytest.mark.db
@needs_db
def test_drafts_bad_tags_and_unknown_surveys_get_no_snippet(client):
    draft = client.post(f"/api/v1/templates/{MEMBER_NPS}/surveys").json()
    r = client.get(f"/api/v1/surveys/{draft['id']}/snippet")
    assert (r.status_code, r.json()["detail"]) == (409, "Publish the survey first.")
    survey = published(client)
    for params in ({"campaign": "Spring 24"}, {"segment": "x" * 41}):
        assert (
            client.get(f"/api/v1/surveys/{survey['id']}/snippet", params=params).status_code == 422
        )
    assert client.get(f"/api/v1/surveys/{uuid4()}/snippet").status_code == 404
