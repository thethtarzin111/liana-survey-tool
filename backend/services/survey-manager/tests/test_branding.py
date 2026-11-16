"""Branding (#66): colours and logo per survey."""

import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from liana_survey_shared.db import ping
from liana_survey_shared.web.auth import CurrentUser, current_user
from liana_survey_shared.web.db import tenant_db
from survey_manager.main import app
from survey_manager.surveys.branding import (
    MAX_LOGO_BYTES,
    LogoError,
    LogoTooLarge,
    check_logo,
    normalise_colour,
)

OTHER_TENANT = UUID("00000000-0000-4000-8000-0000000000ff")
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 20
SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    b'<rect width="10" height="10"/></svg>'
)

needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- Rules ----------------------------------------------------------------------


def test_colours_are_six_digit_hex_codes():
    assert normalise_colour("#2b6450") == "#2B6450"
    assert normalise_colour(" 2B6450 ") == "#2B6450"
    for bad in ("#FFF", "red", "#12345G", "#1234567", ""):
        with pytest.raises(ValueError):
            normalise_colour(bad)


@pytest.mark.parametrize(
    ("kind", "data"),
    [
        ("image/png", PNG),
        ("image/jpeg", JPEG),
        ("image/jpg", JPEG),
        ("image/webp", WEBP),
        ("image/svg+xml", SVG),
    ],
)
def test_accepted_logo_types(kind, data):
    assert check_logo(kind, data) == ("image/jpeg" if kind == "image/jpg" else kind)


@pytest.mark.parametrize(
    ("kind", "data"),
    [
        ("image/gif", b"GIF89a"),  # not an accepted type
        ("application/pdf", b"%PDF"),
        ("image/png", JPEG),  # bytes do not match the type
        ("image/jpeg", PNG),
        ("image/webp", PNG),
        ("image/svg+xml", b"<html>not an svg</html>"),
        ("image/svg+xml", b"\xff\xfe\x00"),  # not text
        ("image/png", b""),
    ],
)
def test_refused_logos(kind, data):
    with pytest.raises(LogoError):
        check_logo(kind, data)


@pytest.mark.parametrize(
    "svg",
    [
        b"<svg><script>alert(1)</script></svg>",
        b'<svg onload="alert(1)"></svg>',
        b'<svg><a href="javascript:alert(1)"/></svg>',
        b"<svg><foreignObject><div/></foreignObject></svg>",
    ],
)
def test_svg_logos_cannot_run_code(svg):
    with pytest.raises(LogoError, match="scripts or event handlers"):
        check_logo("image/svg+xml", svg)


def test_logos_are_at_most_1_mb():
    assert check_logo("image/png", PNG + b"\x00" * (MAX_LOGO_BYTES - len(PNG)))
    with pytest.raises(LogoTooLarge):
        check_logo("image/png", PNG + b"\x00" * MAX_LOGO_BYTES)


# --- API without a database ---------------------------------------------------------


def test_bad_colours_and_uploads_are_refused_before_saving(client):
    app.dependency_overrides[tenant_db] = lambda: None
    url = f"/api/v1/surveys/{uuid4()}"
    assert client.patch(url, json={"accent_color": "teal"}).status_code == 422
    assert client.patch(url, json={"background_color": None}).status_code == 422
    r = client.put(f"{url}/logo", content=b"GIF89a", headers={"Content-Type": "image/gif"})
    assert r.status_code == 415
    big = PNG + b"\x00" * MAX_LOGO_BYTES
    r = client.put(f"{url}/logo", content=big, headers={"Content-Type": "image/png"})
    assert r.status_code == 413


# --- API with a database --------------------------------------------------------------


def new_survey(client) -> dict:
    return client.post("/api/v1/surveys", json={"type": "nps", "title": "Branding test"}).json()


@pytest.mark.db
@needs_db
def test_colours_default_to_teal_on_white_and_are_saved(client):
    survey = new_survey(client)
    assert (survey["accent_color"], survey["background_color"], survey["logo_url"]) == (
        "#0F6A5E",
        "#FFFFFF",
        None,
    )
    url = f"/api/v1/surveys/{survey['id']}"
    r = client.patch(url, json={"accent_color": "#1b4f9c", "background_color": "F0F9F6"})
    assert r.status_code == 200
    assert (r.json()["accent_color"], r.json()["background_color"]) == ("#1B4F9C", "#F0F9F6")
    assert client.get(url).json()["accent_color"] == "#1B4F9C"


@pytest.mark.db
@needs_db
def test_logo_can_be_uploaded_read_replaced_and_removed(client):
    survey = new_survey(client)
    url = f"/api/v1/surveys/{survey['id']}"

    r = client.put(f"{url}/logo", content=PNG, headers={"Content-Type": "image/png"})
    assert r.status_code == 200
    logo_url = r.json()["logo_url"]
    assert logo_url.startswith(f"{url}/logo?v=")
    assert client.get(url).json()["logo_url"] == logo_url

    logo = client.get(logo_url)
    assert logo.status_code == 200
    assert logo.content == PNG
    assert logo.headers["content-type"] == "image/png"
    assert "sandbox" in logo.headers["content-security-policy"]
    assert logo.headers["x-content-type-options"] == "nosniff"

    r = client.put(f"{url}/logo", content=SVG, headers={"Content-Type": "image/svg+xml"})
    assert r.status_code == 200
    assert client.get(f"{url}/logo").headers["content-type"] == "image/svg+xml"

    assert client.delete(f"{url}/logo").status_code == 204
    assert client.get(url).json()["logo_url"] is None
    assert client.get(f"{url}/logo").status_code == 404
    assert client.delete(f"{url}/logo").status_code == 204  # nothing left to remove


@pytest.mark.db
@needs_db
def test_logo_for_unknown_survey_is_404(client):
    url = f"/api/v1/surveys/{uuid4()}/logo"
    assert client.put(url, content=PNG, headers={"Content-Type": "image/png"}).status_code == 404
    assert client.get(url).status_code == 404
    assert client.delete(url).status_code == 404


@pytest.mark.db
@needs_db
def test_duplicate_copies_branding_and_logo(client):
    survey = new_survey(client)
    url = f"/api/v1/surveys/{survey['id']}"
    client.patch(url, json={"accent_color": "#7A2E6E"})
    client.put(f"{url}/logo", content=PNG, headers={"Content-Type": "image/png"})

    copy = client.post(f"{url}/duplicate").json()
    assert copy["accent_color"] == "#7A2E6E"
    assert copy["logo_url"] is not None
    assert client.get(f"/api/v1/surveys/{copy['id']}/logo").content == PNG


@pytest.mark.db
@needs_db
def test_other_organisations_cannot_see_or_change_a_logo(client):
    survey = new_survey(client)
    url = f"/api/v1/surveys/{survey['id']}/logo"
    client.put(url, content=PNG, headers={"Content-Type": "image/png"})

    app.dependency_overrides[current_user] = lambda: CurrentUser(
        user_id=uuid4(),
        tenant_id=OTHER_TENANT,
        tenant_name="Other",
        name="Other user",
        email="other@example.org",
    )
    assert client.get(url).status_code == 404
    assert (
        client.put(url, content=SVG, headers={"Content-Type": "image/svg+xml"}).status_code == 404
    )
    assert client.delete(url).status_code == 404

    app.dependency_overrides.clear()
    assert client.get(url).content == PNG
