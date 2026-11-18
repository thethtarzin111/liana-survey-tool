"""Fixed texts readers see, in English, Finnish and Swedish."""

import pytest

from liana_survey_shared.texts import TEXTS, Language, language_or_default, text


def test_every_text_has_every_language():
    for key, versions in TEXTS.items():
        assert set(versions) == set(Language), key
        assert all(v.strip() for v in versions.values()), key


def test_texts_come_in_the_survey_language():
    assert text("thanks_heading", "en") == "Thank you!"
    assert text("thanks_heading", "fi") == "Kiitos!"
    assert text("thanks_heading", "sv") == "Tack!"


@pytest.mark.parametrize("language", [None, "", "de", "EN"])
def test_unknown_languages_fall_back_to_english(language):
    assert language_or_default(language) is Language.en
    assert text("closed", language) == text("closed", "en")
