from uuid import uuid4

import pytest
from pydantic import ValidationError

from liana_survey_shared.messages import (
    AnswerSubmitted,
    AnswerValue,
    ContactRequested,
    NewResponsesDigest,
)


@pytest.mark.parametrize("segment", ["none", "other", "Bad!", "-x", "x" * 41, ""])
def test_answer_submitted_refuses_invalid_or_reserved_segments(segment):
    with pytest.raises(ValidationError):
        AnswerSubmitted(
            tenant_id=uuid4(),
            survey_id=uuid4(),
            link_token_hash="abc",
            segment=segment,
            answers=[AnswerValue(question_id=uuid4(), number=9)],
        )


def test_answer_submitted_round_trips_through_json():
    msg = AnswerSubmitted(
        tenant_id=uuid4(),
        survey_id=uuid4(),
        link_token_hash="abc",
        answers=[AnswerValue(question_id=uuid4(), number=9)],
    )
    again = AnswerSubmitted.model_validate_json(msg.model_dump_json())
    assert again == msg
    assert again.contact_ref is None  # anonymous by default


def test_message_types_are_fixed():
    msg = ContactRequested(
        tenant_id=uuid4(), survey_id=uuid4(), contact_request_id=uuid4(), contact_ref="c1"
    )
    assert msg.type == "contact.requested"


def test_a_new_responses_digest_needs_at_least_one_new_response():
    fields = {
        "tenant_id": uuid4(),
        "survey_id": uuid4(),
        "survey_title": "Poll",
        "total_responses": 3,
        "results_url": "http://localhost:4200/results",
        "recipient_email": "anna.virtanen@example.org",
        "recipient_name": "Anna Virtanen",
    }
    msg = NewResponsesDigest(new_responses=2, **fields)
    assert msg.type == "responses.digest"
    assert NewResponsesDigest.model_validate_json(msg.model_dump_json()) == msg
    with pytest.raises(ValidationError):
        NewResponsesDigest(new_responses=0, **fields)


def test_answers_carry_a_valid_campaign_tag_and_a_short_comment():
    from uuid import uuid4

    import pydantic

    from liana_survey_shared.messages import AnswerSubmitted

    fields = {"tenant_id": uuid4(), "survey_id": uuid4(), "link_token_hash": "k", "answers": []}
    answer = AnswerSubmitted(**fields, campaign="test-november-customer-survey", comment="Hi")
    assert (answer.campaign, answer.comment, answer.contact_me) == (
        "test-november-customer-survey",
        "Hi",
        False,
    )
    for bad in ({"campaign": "Not a tag"}, {"comment": "x" * 5001}):
        with pytest.raises(pydantic.ValidationError):
            AnswerSubmitted(**fields, **bad)
