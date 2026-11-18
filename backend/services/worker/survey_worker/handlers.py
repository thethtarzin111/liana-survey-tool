"""What the worker does with each message (#23). Kept free of RabbitMQ code so it
can be tested on its own."""

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from liana_survey_shared.db import tenant_connection
from liana_survey_shared.messages import AnswerSubmitted

log = logging.getLogger(__name__)

Connect = Callable[[UUID], AbstractContextManager[psycopg.Connection]]

#: Main questions whose answers are counted per value in survey_aggregates.distribution,
#: which the scoring rules (liana_survey_shared.scoring) read.
SCALE_KINDS = frozenset({"thumbs", "nps", "rating"})


class BadMessage(Exception):
    """The message can never be saved (wrong shape, unknown survey or question).
    It goes to the dead-letter queue instead of being retried."""


def parse(body: bytes) -> AnswerSubmitted:
    try:
        return AnswerSubmitted.model_validate_json(body)
    except ValidationError as error:
        raise BadMessage(
            f"not an AnswerSubmitted message ({error.error_count()} errors)"
        ) from error


def handle_answer(body: bytes, connect: Connect = tenant_connection) -> bool:
    """Save one answer and update the survey's totals, in one transaction.

    Returns False when this reader's answer was already saved (the same message
    delivered twice, or the same link opened twice): it is counted once.
    Raises BadMessage for messages that can never be saved."""
    msg = parse(body)
    try:
        with connect(msg.tenant_id) as conn:
            saved = _save(conn, msg)
    except (psycopg.errors.ForeignKeyViolation, psycopg.errors.DataError) as error:
        raise BadMessage(f"answer does not fit the survey: {error.diag.message_primary}") from error
    log.info(
        "answer %s survey=%s message=%s",
        "saved" if saved else "already saved",
        msg.survey_id,
        msg.message_id,
    )
    return saved


def _save(conn: psycopg.Connection, msg: AnswerSubmitted) -> bool:
    # Row-level security limits this connection to the message's tenant, so a
    # survey of another tenant looks like an unknown survey.
    if conn.execute("select 1 from surveys where id = %s", (msg.survey_id,)).fetchone() is None:
        raise BadMessage("unknown survey")

    response = conn.execute(
        """insert into responses
             (tenant_id, survey_id, submitted_at, link_token_hash, contact_ref, segment)
           values (%s, %s, %s, %s, %s, %s)
           on conflict (survey_id, link_token_hash) do nothing
           returning id""",
        (
            msg.tenant_id,
            msg.survey_id,
            msg.created_at,
            msg.link_token_hash,
            msg.contact_ref,
            msg.segment,
        ),
    ).fetchone()
    if response is None:
        return False

    for answer in msg.answers:
        stored = conn.execute(
            """insert into answers
                 (tenant_id, response_id, question_id, value_number, value_text, value_choices)
               select %s, %s, q.id, %s, %s, %s
               from questions q where q.id = %s and q.survey_id = %s""",
            (
                msg.tenant_id,
                response[0],
                answer.number,
                answer.text,
                Jsonb(answer.choices) if answer.choices is not None else None,
                answer.question_id,
                msg.survey_id,
            ),
        ).rowcount
        if stored != 1:
            raise BadMessage("answer for a question that is not in this survey")

    conn.execute(
        """insert into survey_aggregates (survey_id, tenant_id, response_count, distribution)
           values (%s, %s, 1, %s)
           on conflict (survey_id) do update set
             response_count = survey_aggregates.response_count + 1,
             distribution = (
               select coalesce(jsonb_object_agg(key, total), '{}'::jsonb)
               from (
                 select key, sum(value::int) as total
                 from (
                   select * from jsonb_each_text(survey_aggregates.distribution)
                   union all
                   select * from jsonb_each_text(excluded.distribution)
                 ) as both_counts
                 group by key
               ) as summed
             ),
             updated_at = now()""",
        (msg.survey_id, msg.tenant_id, Jsonb(_main_question_count(conn, msg))),
    )
    return True


def _main_question_count(conn: psycopg.Connection, msg: AnswerSubmitted) -> dict[str, int]:
    """{"9": 1} when this response gives 9 to the survey's main scale question, else {}."""
    main = conn.execute(
        "select id, kind from questions where survey_id = %s order by position limit 1",
        (msg.survey_id,),
    ).fetchone()
    if main is None or main[1] not in SCALE_KINDS:
        return {}
    for answer in msg.answers:
        if answer.question_id == main[0] and answer.number is not None:
            return {str(int(answer.number)): 1}
    return {}
