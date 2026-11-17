from urllib.parse import parse_qs, urlsplit

import pytest

from liana_survey_shared.links import (
    LinkError,
    answer_link,
    check_signature,
    response_key,
    signature,
)

SECRET = "test-secret"


def test_answer_links_carry_the_reader_and_a_valid_signature():
    url = answer_link("https://survey.example.eu/", SECRET, "tok123", "contact-42")
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://survey.example.eu/r/tok123"
    query = parse_qs(parts.query)
    assert query["r"] == ["contact-42"]
    check_signature(SECRET, "tok123", "contact-42", query["s"][0])


@pytest.mark.parametrize(
    ("token", "ref", "secret"),
    [
        ("other", "contact-42", SECRET),
        ("tok123", "contact-43", SECRET),
        ("tok123", "contact-42", "x"),
    ],
)
def test_signatures_only_fit_their_own_survey_reader_and_secret(token, ref, secret):
    sig = signature(SECRET, "tok123", "contact-42")
    with pytest.raises(LinkError):
        check_signature(secret, token, ref, sig)


@pytest.mark.parametrize("sig", ["", "abc", None])
def test_missing_or_short_signatures_are_refused(sig):
    with pytest.raises(LinkError):
        check_signature(SECRET, "tok123", "contact-42", sig)


@pytest.mark.parametrize("ref", ["", "has space", "a/b", "x" * 65, "anna@example.org"])
def test_reader_refs_are_short_plain_ids(ref):
    with pytest.raises(LinkError):
        answer_link("https://x", SECRET, "tok123", ref)
    with pytest.raises(LinkError):
        check_signature(SECRET, "tok123", ref, "sig")


def test_response_keys_are_stable_per_reader_and_hide_the_reference():
    key = response_key(SECRET, "tok123", "contact-42")
    assert key == response_key(SECRET, "tok123", "contact-42")
    assert key != response_key(SECRET, "tok123", "contact-43")
    assert key != response_key(SECRET, "tok999", "contact-42")
    assert "contact-42" not in key
    assert key != signature(SECRET, "tok123", "contact-42")
