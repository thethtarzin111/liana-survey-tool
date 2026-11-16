from uuid import uuid4

from liana_survey_shared.messages import AnswerSubmitted, AnswerValue, ContactRequested


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
