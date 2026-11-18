"""What the worker does with each message (#23). Kept free of RabbitMQ code so it
can be tested on its own."""

import logging
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from liana_survey_shared.db import tenant_connection
from liana_survey_shared.messages import AnswerSubmitted, NewResponsesDigest

from .digests import claim_digest

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


@dataclass(frozen=True)
class Recorded:
    #: False when nothing changed (see handle_answer).
    changed: bool
    #: The "new responses" email to publish now, if one is due.
    digest: NewResponsesDigest | None = None


def handle_answer(body: bytes, connect: Connect = tenant_connection) -> bool:
    """Save one answer and update the survey's totals, in one transaction.

    Each reader counts once, and their latest tap wins (#126): an answer from a
    reader who already answered replaces the earlier one if it is newer, and the
    totals move with it. Mail scanners open every link on delivery; the person
    taps later, so their answer is the one kept.

    No answers are taken from the survey's close date on, and no new readers once
    its response limit is reached (#47).

    Returns False when nothing changed: the same message delivered twice, an
    older answer arriving after a newer one, or a closed or full survey. Raises
    BadMessage for messages that can never be saved."""
    return record_answer(body, connect).changed


def record_answer(body: bytes, connect: Connect = tenant_connection) -> Recorded:
    """handle_answer(), plus the owner's "new responses" email when a new reader's
    answer makes one due. It is claimed in the same transaction as the answer."""
    msg = parse(body)
    digest = None
    try:
        with connect(msg.tenant_id) as conn:
            outcome = _save(conn, msg)
            if outcome == "saved":
                digest = claim_digest(conn, msg.survey_id, after_new_response=True)
    except (psycopg.errors.ForeignKeyViolation, psycopg.errors.DataError) as error:
        raise BadMessage(f"answer does not fit the survey: {error.diag.message_primary}") from error
    log.info("answer %s survey=%s message=%s", outcome, msg.survey_id, msg.message_id)
    return Recorded(outcome in ("saved", "replaced"), digest)


def _save(conn: psycopg.Connection, msg: AnswerSubmitted) -> str:
    """What happened: "saved" or "replaced", or why nothing changed: "kept" (the
    stored answer is as new or newer), "closed" (tapped on or after the close
    date) or "full" (a new reader once the response limit is reached)."""
    # Row-level security limits this connection to the message's tenant, so a
    # survey of another tenant looks like an unknown survey.
    survey = conn.execute(
        "select closes_at, response_limit from surveys where id = %s", (msg.survey_id,)
    ).fetchone()
    if survey is None:
        raise BadMessage("unknown survey")
    closes_at, response_limit = survey
    # The reader's tap time decides, not when the worker gets to the message.
    if closes_at is not None and msg.created_at >= closes_at:
        return "closed"
    main = _main_question(conn, msg.survey_id)
    new_count = _main_count(main, [(a.question_id, a.number) for a in msg.answers])

    inserted = conn.execute(
        """insert into responses
             (tenant_id, survey_id, submitted_at, link_token_hash, contact_ref, channel, segment)
           values (%s, %s, %s, %s, %s, %s, %s)
           on conflict (survey_id, link_token_hash) do nothing
           returning id""",
        (
            msg.tenant_id,
            msg.survey_id,
            msg.created_at,
            msg.link_token_hash,
            msg.contact_ref,
            msg.channel,
            msg.segment,
        ),
    ).fetchone()
    if inserted is not None:
        if not _add_to_totals(conn, msg, new_count, new_reader=True, limit=response_limit):
            conn.execute("delete from responses where id = %s", (inserted[0],))
            return "full"
        _save_answers(conn, msg, inserted[0])
        return "saved"

    # This reader answered before. Lock their response so two taps at the same
    # time can't both replace it.
    response_id, submitted_at = conn.execute(
        """select id, submitted_at from responses
           where survey_id = %s and link_token_hash = %s for update""",
        (msg.survey_id, msg.link_token_hash),
    ).fetchone()
    if msg.created_at <= submitted_at:
        return "kept"

    old_answers = conn.execute(
        "select question_id, value_number from answers where response_id = %s", (response_id,)
    ).fetchall()
    old_count = _main_count(main, old_answers)
    conn.execute("delete from answers where response_id = %s", (response_id,))
    conn.execute(
        """update responses set submitted_at = %s, contact_ref = coalesce(%s, contact_ref)
           where id = %s""",
        (msg.created_at, msg.contact_ref, response_id),
    )
    _save_answers(conn, msg, response_id)
    change = dict(new_count)
    for value, count in old_count.items():
        change[value] = change.get(value, 0) - count
    _add_to_totals(conn, msg, change, new_reader=False)
    return "replaced"


def _save_answers(conn: psycopg.Connection, msg: AnswerSubmitted, response_id: UUID) -> None:
    for answer in msg.answers:
        stored = conn.execute(
            """insert into answers
                 (tenant_id, response_id, question_id, value_number, value_text, value_choices)
               select %s, %s, q.id, %s, %s, %s
               from questions q where q.id = %s and q.survey_id = %s""",
            (
                msg.tenant_id,
                response_id,
                answer.number,
                answer.text,
                Jsonb(answer.choices) if answer.choices is not None else None,
                answer.question_id,
                msg.survey_id,
            ),
        ).rowcount
        if stored != 1:
            raise BadMessage("answer for a question that is not in this survey")


def _add_to_totals(
    conn: psycopg.Connection,
    msg: AnswerSubmitted,
    distribution: dict[str, int],
    *,
    new_reader: bool,
    limit: int | None = None,
) -> bool:
    """Add to the count per value and, for a new reader, to the response count.
    Values that reach 0 are left out of the distribution.

    Returns False, changing nothing, when a new reader would go past `limit`. The
    check and the update are one statement on the locked totals row, so two
    answers at the same time can't both take the last place."""
    conn.execute(
        """insert into survey_aggregates (survey_id, tenant_id) values (%s, %s)
           on conflict (survey_id) do nothing""",
        (msg.survey_id, msg.tenant_id),
    )
    updated = conn.execute(
        """update survey_aggregates set
             response_count = response_count + %(added)s,
             distribution = (
               select coalesce(jsonb_object_agg(key, total), '{}'::jsonb)
               from (
                 select key, sum(value::int) as total
                 from (
                   select * from jsonb_each_text(survey_aggregates.distribution)
                   union all
                   select * from jsonb_each_text(%(change)s)
                 ) as both_counts
                 group by key
                 having sum(value::int) <> 0
               ) as summed
             ),
             updated_at = now()
           where survey_id = %(survey)s
             and (%(limit)s::int is null or response_count + %(added)s <= %(limit)s)
           returning 1""",
        {
            "added": 1 if new_reader else 0,
            "change": Jsonb(distribution),
            "survey": msg.survey_id,
            "limit": limit if new_reader else None,
        },
    ).fetchone()
    return updated is not None


def _main_question(conn: psycopg.Connection, survey_id: UUID) -> UUID | None:
    """The survey's main question, if it is a scale counted per value."""
    main = conn.execute(
        "select id, kind from questions where survey_id = %s order by position limit 1",
        (survey_id,),
    ).fetchone()
    return main[0] if main is not None and main[1] in SCALE_KINDS else None


def _main_count(
    main: UUID | None, answers: Iterable[tuple[UUID, float | Decimal | None]]
) -> dict[str, int]:
    """{"9": 1} when these (question id, number) pairs give 9 to the main scale
    question, else {}."""
    if main is None:
        return {}
    for question_id, number in answers:
        if question_id == main and number is not None:
            return {str(int(number)): 1}
    return {}
