"""What the worker does with each message. Kept free of RabbitMQ code so it
can be tested on its own."""

import logging

from liana_survey_shared.messages import AnswerSubmitted

log = logging.getLogger(__name__)


def handle_answer(body: bytes) -> AnswerSubmitted:
    """Parse and (later) save one answer.

    TODO (backlog card "Save answers and update totals"): insert into
    responses/answers through tenant_connection(), update survey_aggregates,
    and publish ContactRequested when the respondent asked to be contacted.
    """
    msg = AnswerSubmitted.model_validate_json(body)
    log.info("answer received survey=%s message=%s (not saved yet)", msg.survey_id, msg.message_id)
    return msg
