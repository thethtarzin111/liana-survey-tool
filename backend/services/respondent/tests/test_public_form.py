from uuid import uuid4

import pytest

from respondent_service.public_form import render, validate


def test_required_and_choice_validation():
    question = dict(
        id=uuid4(), kind="single_choice", prompt="Choose", options=["Yes"], required=True
    )
    with pytest.raises(ValueError):
        validate([question], {}, "custom")
    with pytest.raises(ValueError):
        validate([question], {str(question["id"]): ["No"]}, "custom")
    assert validate([question], {str(question["id"]): ["Yes"]}, "custom")[0].choices == ["Yes"]


def test_template_internal_name_is_private_and_text_is_escaped():
    survey = dict(
        title="PRIVATE",
        reader_title="<Welcome>",
        type="nps",
        description="<script>",
        background_color="#FFFFFF",
    )
    page = render(survey, [], "key")
    assert "PRIVATE" not in page
    assert "&lt;Welcome&gt;" in page
    assert "&lt;script&gt;" in page
