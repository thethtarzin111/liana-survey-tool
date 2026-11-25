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
from liana_survey_shared.messages import (
    AnswerRecorded,
    AnswerSubmitted,
    ContactRequested,
    Message,
    NewResponsesDigest,
)

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
    #: For the Liana connector: the saved answer (AnswerRecorded) and, when the
    #: reader ticked "Contact me", their new contact request (ContactRequested).
    events: tuple[Message, ...] = ()


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
    """handle_answer(), plus what to publish after it, all decided in the answer's
    transaction:

    - the owner's "new responses" email when a new reader's answer makes one due;
    - AnswerRecorded for every saved or changed answer, so the connector can send
      it to LianaAutomation (or say in the sync log why not);
    - ContactRequested when the reader ticked "Contact me": the request is saved on
      the response (Results -> Responses, "Asked to be contacted") and as a contact
      request here, once per response, whether or not it reaches LianaAutomation."""
    msg = parse(body)
    digest = None
    events: list[Message] = []
    try:
        with connect(msg.tenant_id) as conn:
            outcome, response_id = _save(conn, msg)
            if outcome == "saved":
                digest = claim_digest(conn, msg.survey_id, after_new_response=True)
            if response_id is not None:
                events.append(_recorded(conn, msg, response_id))
                if msg.contact_me:
                    request = _request_contact(conn, msg, response_id)
                    if request is not None:
                        events.append(request)
    except (psycopg.errors.ForeignKeyViolation, psycopg.errors.DataError) as error:
        raise BadMessage(f"answer does not fit the survey: {error.diag.message_primary}") from error
    log.info("answer %s survey=%s message=%s", outcome, msg.survey_id, msg.message_id)
    return Recorded(outcome in ("saved", "replaced"), digest, tuple(events))


def _recorded(conn: psycopg.Connection, msg: AnswerSubmitted, response_id: UUID) -> AnswerRecorded:
    """The saved answer for the connector: the main answer and the contact the
    response now has (an earlier "Contact me" keeps it when the reader taps again)."""
    title, contact_ref = conn.execute(
        """select s.title, r.contact_ref from responses r join surveys s on s.id = r.survey_id
           where r.id = %s""",
        (response_id,),
    ).fetchone()
    main = conn.execute(
        "select id, kind::text from questions where survey_id = %s order by position limit 1",
        (msg.survey_id,),
    ).fetchone()
    score = None
    if main is not None:
        for answer in msg.answers:
            if answer.question_id == main[0] and answer.number is not None:
                score = int(answer.number)
    return AnswerRecorded(
        tenant_id=msg.tenant_id,
        survey_id=msg.survey_id,
        response_id=response_id,
        survey_title=title,
        main_kind=main[1] if main is not None else None,
        score=score,
        campaign=msg.campaign,
        contact_ref=contact_ref,
    )


def _request_contact(
    conn: psycopg.Connection, msg: AnswerSubmitted, response_id: UUID
) -> ContactRequested | None:
    """Create the response's contact request, or None if it already has one or there
    is no way to reach the reader (no contact id, no address)."""
    contact_ref, contact_email = conn.execute(
        "select contact_ref, contact_email from responses where id = %s", (response_id,)
    ).fetchone()
    if not (contact_ref or contact_email):
        return None
    row = conn.execute(
        """insert into contact_requests (tenant_id, survey_id, response_id, contact_ref)
           values (%s, %s, %s, %s)
           on conflict (response_id) do nothing
           returning id""",
        (msg.tenant_id, msg.survey_id, response_id, contact_ref),
    ).fetchone()
    if row is None:
        return None
    return ContactRequested(
        tenant_id=msg.tenant_id,
        survey_id=msg.survey_id,
        contact_request_id=row[0],
        contact_ref=contact_ref,
        contact_email=contact_email,
        response_id=response_id,
    )


def _save(conn: psycopg.Connection, msg: AnswerSubmitted) -> tuple[str, UUID | None]:
    """What happened, and the response it happened to: "saved" or "replaced", or
    why nothing changed: "kept" (the stored answer is as new or newer), "closed"
    (tapped on or after the close date) or "full" (a new reader once the response
    limit is reached). The response is None when nothing changed."""
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
        return "closed", None
    main = _main_question(conn, msg.survey_id)
    new_count = _main_count(main, [(a.question_id, a.number) for a in msg.answers])

    inserted = conn.execute(
        """insert into responses
             (tenant_id, survey_id, submitted_at, link_token_hash, contact_ref, channel, segment,
              comment, contact_requested, contact_requested_at, contact_email)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                   case when %s then %s::timestamptz end, %s)
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
            msg.comment,
            msg.contact_me,
            msg.contact_me,
            msg.created_at,
            msg.contact_email if msg.contact_me else None,
        ),
    ).fetchone()
    if inserted is not None:
        if not _add_to_totals(conn, msg, new_count, new_reader=True, limit=response_limit):
            conn.execute("delete from responses where id = %s", (inserted[0],))
            return "full", None
        _save_answers(conn, msg, inserted[0])
        return "saved", inserted[0]

    # This reader answered before. Lock their response so two taps at the same
    # time can't both replace it.
    response_id, submitted_at = conn.execute(
        """select id, submitted_at from responses
           where survey_id = %s and link_token_hash = %s for update""",
        (msg.survey_id, msg.link_token_hash),
    ).fetchone()
    if msg.created_at <= submitted_at:
        return "kept", None

    old_answers = conn.execute(
        "select question_id, value_number from answers where response_id = %s", (response_id,)
    ).fetchall()
    old_count = _main_count(main, old_answers)
    if msg.main_only:
        # The follow-up page saving the tapped answer again (the reader opened the
        # link again): their other answers from the follow-up form stay.
        conn.execute(
            "delete from answers where response_id = %s and question_id = any(%s)",
            (response_id, [answer.question_id for answer in msg.answers]),
        )
    else:
        conn.execute("delete from answers where response_id = %s", (response_id,))
    conn.execute(
        # Nothing here takes a contact or a "Contact me" away: an unticked box on a
        # later form, or a later tap, keeps the earlier request.
        """update responses set
             submitted_at = %(at)s,
             contact_ref = coalesce(%(ref)s, contact_ref),
             comment = coalesce(%(comment)s, comment),
             contact_requested = contact_requested or %(asked)s,
             contact_requested_at = coalesce(contact_requested_at,
                                             case when %(asked)s then %(at)s::timestamptz end),
             contact_email = coalesce(%(email)s, contact_email)
           where id = %(id)s""",
        {
            "at": msg.created_at,
            "ref": msg.contact_ref,
            "comment": msg.comment,
            "asked": msg.contact_me,
            "email": msg.contact_email if msg.contact_me else None,
            "id": response_id,
        },
    )
    _save_answers(conn, msg, response_id)
    change = dict(new_count)
    for value, count in old_count.items():
        change[value] = change.get(value, 0) - count
    _add_to_totals(conn, msg, change, new_reader=False)
    return "replaced", response_id


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
