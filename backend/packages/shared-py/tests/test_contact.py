import pytest

from liana_survey_shared.contact import InvalidEmail, answer_contact_ref, clean_email


def test_an_answer_from_a_newsletter_link_keeps_its_contact_id():
    assert answer_contact_ref(" 4084399 ") == "4084399"


@pytest.mark.parametrize("ref", [None, "", "   "])
def test_without_a_contact_id_the_answer_is_anonymous(ref):
    assert answer_contact_ref(ref) is None


@pytest.mark.parametrize("ref", ["anna.virtanen@example.org", "x <a@b.fi>"])
def test_an_email_address_is_never_taken_as_a_contact_id(ref):
    assert answer_contact_ref(ref) is None


def test_a_typed_email_address_is_trimmed_and_lower_cased():
    assert clean_email("  Anna.Virtanen@Example.org ") == "anna.virtanen@example.org"


@pytest.mark.parametrize(
    "value", [None, "", "anna", "anna@", "anna@example", "a b@example.org", "a@b@example.org"]
)
def test_an_address_nobody_can_be_reached_at_is_refused(value):
    with pytest.raises(InvalidEmail):
        clean_email(value)


def test_an_overlong_address_is_refused():
    with pytest.raises(InvalidEmail):
        clean_email("a" * 250 + "@example.org")
