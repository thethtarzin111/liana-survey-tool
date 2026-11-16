from uuid import uuid4

import pytest
from pydantic import ValidationError

from liana_survey_shared.messages import AnswerSubmitted, AnswerValue
from survey_worker.handlers import handle_answer


def test_handle_answer_parses_message():
    msg = AnswerSubmitted(
        tenant_id=uuid4(),
        survey_id=uuid4(),
        link_token_hash="h",
        answers=[AnswerValue(question_id=uuid4(), number=4)],
    )
    assert handle_answer(msg.model_dump_json().encode()) == msg


def test_handle_answer_rejects_garbage():
    with pytest.raises(ValidationError):
        handle_answer(b'{"nope": 1}')
