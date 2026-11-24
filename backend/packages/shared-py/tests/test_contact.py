import pytest

from liana_survey_shared.contact import (
    ContactRefError,
    answer_contact_ref,
    contact_ref_to_store,
)


def test_answers_stay_anonymous_without_both_opt_ins():
    # The survey must offer the opt-in and the reader must tick it.
    assert contact_ref_to_store(False, True, "lm-contact-42") is None
    assert contact_ref_to_store(True, False, "lm-contact-42") is None
    assert contact_ref_to_store(False, False, None) is None


def test_an_opted_in_reader_is_linked_by_contact_reference():
    assert contact_ref_to_store(True, True, "  lm-contact-42 ") == "lm-contact-42"


@pytest.mark.parametrize("ref", [None, "", "   "])
def test_opting_in_needs_a_reference(ref):
    with pytest.raises(ContactRefError):
        contact_ref_to_store(True, True, ref)


@pytest.mark.parametrize("ref", ["anna.virtanen@example.org", "x <a@b.fi>"])
def test_email_addresses_are_never_stored(ref):
    with pytest.raises(ContactRefError, match="never an e-mail address"):
        contact_ref_to_store(True, True, ref)


def ref(identified=False, offered=True, ticked=False, contact="4084399"):
    return answer_contact_ref(
        identified_survey=identified,
        survey_offers_opt_in=offered,
        reader_opted_in=ticked,
        contact_ref=contact,
    )


def test_answers_stay_anonymous_unless_identified_or_contact_me():
    assert ref() is None
    assert ref(ticked=True) == "4084399"
    assert ref(offered=False, ticked=True) is None  # ticked a box the survey does not offer
    assert ref(identified=True) == "4084399"


def test_without_a_usable_contact_the_answer_stays_anonymous():
    assert ref(identified=True, contact=None) is None
    assert ref(identified=True, contact="  ") is None
    assert ref(ticked=True, contact="anna@example.com") is None
