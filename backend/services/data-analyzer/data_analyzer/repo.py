from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg

from .domain import EMAIL_PATTERN, EMAIL_REPLACEMENT, PHONE_PATTERN, PHONE_REPLACEMENT


def performance_rows(
    conn: psycopg.Connection, *, limit: int | None = None, offset: int = 0
) -> list[dict[str, Any]]:
    """Views, responses and the main question's answer counts per survey and channel.

    Surveys with the latest view or answer come first. `limit` and `offset` count
    surveys, so a survey's channel rows stay together. `distribution` only counts
    the answers that came through that channel, so each row's main result is the
    channel's own."""
    return conn.execute(
        """with active as (
             select s.id, greatest(
                      (select max(v.updated_at) from survey_channel_views v
                       where v.survey_id = s.id and v.view_count > 0),
                      (select max(r.submitted_at) from responses r where r.survey_id = s.id)
                    ) as last_activity
             from surveys s
             where exists (select 1 from survey_channel_views v
                           where v.survey_id = s.id and v.view_count > 0)
                or exists (select 1 from responses r where r.survey_id = s.id)
             order by last_activity desc nulls last, s.id
             limit %(limit)s offset %(offset)s
           )
           select s.id as survey_id, s.title as survey, s.type,
                  channels.channel::text as channel,
                  coalesce(v.view_count, 0) as views,
                  coalesce(r.responses, 0) as responses,
                  coalesce(d.distribution, '{}'::jsonb) as distribution
           from active
           join surveys s on s.id = active.id
           cross join unnest(enum_range(null::distribution_channel)) channels(channel)
           left join survey_channel_views v
             on v.survey_id = s.id and v.channel = channels.channel
           left join (
             select survey_id, channel, count(*)::integer as responses
             from responses group by survey_id, channel
           ) r on r.survey_id = s.id and r.channel = channels.channel
           left join lateral (
             select jsonb_object_agg(value, n) as distribution
             from (
               select a.value_number::integer::text as value, count(*)::integer as n
               from responses rr
               join answers a on a.response_id = rr.id
               where rr.survey_id = s.id and rr.channel = channels.channel
                 and a.value_number is not null
                 and a.question_id = (
                   select q.id from questions q where q.survey_id = s.id
                   order by q.position limit 1
                 )
               group by 1
             ) counts
           ) d on true
           where coalesce(v.view_count, 0) > 0 or coalesce(r.responses, 0) > 0
           order by active.last_activity desc nulls last, s.id, channels.channel""",
        {"limit": limit, "offset": offset},
    ).fetchall()


def segment_counts(conn: psycopg.Connection, survey_id: UUID) -> dict[str, int] | None:
    """Responses per stored segment, or None when the survey is not found."""
    if conn.execute("select 1 from surveys where id = %s", (survey_id,)).fetchone() is None:
        return None
    return {
        row["segment"]: row["n"]
        for row in conn.execute(
            """select segment, count(*)::integer as n from responses
               where survey_id = %s group by segment""",
            (survey_id,),
        ).fetchall()
    }


SCALE_KINDS = ("nps", "thumbs", "rating")
TEXT_KINDS = ("text", "long_text")


def overview_rows(
    conn: psycopg.Connection,
    survey_id: UUID,
    stored: tuple[str, ...] | None,
    time_zone: str = "Europe/Helsinki",
) -> dict[str, Any] | None:
    """What the survey overview needs, in a few queries however many questions there are.

    `stored` limits the per-question numbers to those stored segments, None means no
    limit. The segment counts and the main question's counts by segment always cover
    every response, because the segment list and the By segment card compare them.
    Months are calendar months in `time_zone`. None when the survey is not found."""
    survey = conn.execute(
        """select s.id, s.title, s.type::text as type, s.status::text as status, s.closes_at,
                  (select max(r.submitted_at) from responses r where r.survey_id = s.id)
                    as last_answer_at,
                  now() as now,
                  coalesce((select sum(v.view_count) from survey_channel_views v
                            where v.survey_id = s.id), 0)::integer as views,
                  array(select c.channel::text
                        from unnest(enum_range(null::distribution_channel)) c(channel)
                        where exists (select 1 from survey_channel_views v
                                      where v.survey_id = s.id and v.channel = c.channel
                                        and v.view_count > 0)
                           or exists (select 1 from responses r
                                      where r.survey_id = s.id and r.channel = c.channel)
                  ) as channels
           from surveys s where s.id = %s""",
        (survey_id,),
    ).fetchone()
    if survey is None:
        return None
    channels = survey.pop("channels")
    views = survey.pop("views")
    now: datetime = survey.pop("now")

    questions = conn.execute(
        """select id, kind::text as kind, prompt, required, options
           from questions where survey_id = %s order by position""",
        (survey_id,),
    ).fetchall()

    counts = segment_counts(conn, survey_id) or {}

    stored_filter = {"survey": survey_id, "stored": list(stored) if stored is not None else None}
    in_segment = "(%(stored)s::text[] is null or r.segment = any(%(stored)s))"

    # Answers per question, and the picked values of the questions that have options or
    # a scale. A multiple-choice answer counts each picked option once.
    answered = {
        str(row["question_id"]): row["n"]
        for row in conn.execute(
            f"""select a.question_id, count(*)::integer as n
                from answers a join responses r on r.id = a.response_id
                where r.survey_id = %(survey)s and {in_segment}
                group by a.question_id""",
            stored_filter,
        ).fetchall()
    }
    values: dict[str, dict[str, int]] = {}
    for row in conn.execute(
        f"""select a.question_id, v.value, count(*)::integer as n
            from answers a
            join responses r on r.id = a.response_id
            join questions q on q.id = a.question_id
            cross join lateral (
              select a.value_number::integer::text as value where a.value_number is not null
              union all
              select a.value_text where a.value_text is not null
              union all
              select jsonb_array_elements_text(a.value_choices)
              where a.value_choices is not null
            ) v
            where r.survey_id = %(survey)s and {in_segment}
              and q.kind::text <> all(%(text)s)
            group by a.question_id, v.value""",
        {**stored_filter, "text": list(TEXT_KINDS)},
    ).fetchall():
        values.setdefault(str(row["question_id"]), {})[row["value"]] = row["n"]

    # The main question's counts by segment and month, for the score, change, trend
    # and By segment. The caller filters by segment.
    main_rows = conn.execute(
        """select r.segment,
                  to_char(r.submitted_at at time zone %(tz)s, 'YYYY-MM') as month,
                  a.value_number::integer::text as value, count(*)::integer as n
           from answers a join responses r on r.id = a.response_id
           where r.survey_id = %(survey)s and a.value_number is not null
             and a.question_id = (select q.id from questions q
                                  where q.survey_id = %(survey)s and q.kind::text = any(%(scale)s)
                                  order by q.position limit 1)
           group by r.segment, month, value""",
        {"survey": survey_id, "tz": time_zone, "scale": list(SCALE_KINDS)},
    ).fetchall()

    completed = conn.execute(
        f"""select count(*)::integer as n from responses r
            where r.survey_id = %(survey)s and {in_segment}
              and (select count(distinct a.question_id) from answers a where a.response_id = r.id)
                  = (select count(*) from questions q where q.survey_id = %(survey)s)""",
        stored_filter,
    ).fetchone()["n"]

    return {
        "survey": survey,
        "now": now,
        "channels": channels,
        "views": views,
        "questions": [{**q, "id": str(q["id"])} for q in questions],
        "segment_counts": counts,
        "answered": answered,
        "values": values,
        "main_rows": main_rows,
        "completed": completed,
    }


def mask_sql(column: str) -> str:
    """SQL that hides emails and phone numbers in `column`, as `domain.mask` does.

    Needs the named parameters `email` and `phone` (see MASK_PARAMS)."""
    return (
        f"regexp_replace(regexp_replace({column}, %(email)s, '{EMAIL_REPLACEMENT}', 'g'),"
        f" %(phone)s, '{PHONE_REPLACEMENT}', 'g')"
    )


MASK_PARAMS = {"email": EMAIL_PATTERN, "phone": PHONE_PATTERN}

# The responses of one survey in the allowed segments, with the main answer, the
# reason and the comment. The comment is masked here, so the search, the counts and
# the paging only ever see the masked text.
_FILTERED = f"""
with picked as (
  select
    (select id from questions where survey_id = %(survey)s and kind::text = any(%(scale)s)
     order by position limit 1) as scale,
    (select id from questions where survey_id = %(survey)s and kind::text = 'reasons'
     order by position limit 1) as reasons,
    (select id from questions where survey_id = %(survey)s and kind::text = any(%(text)s)
     order by position limit 1) as comment
), base as (
  select r.id, r.submitted_at, r.segment,
    r.contact_requested, r.contact_ref, r.contact_email,
    (select a.value_number::integer from answers a
     where a.response_id = r.id and a.question_id = picked.scale limit 1) as answer,
    (select case when a.value_choices is not null
                 then (select string_agg(c.value, '; ' order by c.ord)
                       from jsonb_array_elements_text(a.value_choices)
                            with ordinality c(value, ord))
                 else a.value_text end
     from answers a where a.response_id = r.id and a.question_id = picked.reasons
     limit 1) as reason,
    -- The survey's own text question, else the "Tell us more" box (responses.comment).
    coalesce((select a.value_text from answers a
              where a.response_id = r.id and a.question_id = picked.comment limit 1),
             r.comment) as raw_comment
  from responses r cross join picked
  where r.survey_id = %(survey)s
    and (%(stored)s::text[] is null or r.segment = any(%(stored)s))
), masked as (
  select base.*, {mask_sql("raw_comment")} as comment from base
), filtered as (
  select masked.*, raw_comment is not null and comment <> raw_comment as was_masked
  from masked
  where (%(search)s::text is null or comment ilike %(search)s)
    and (%(group)s::integer[] is null or answer = any(%(group)s))
    and (not %(contact)s or contact_requested)
)
"""


def _filter_params(
    survey_id: UUID,
    stored: tuple[str, ...] | None,
    search: str | None,
    group: tuple[int, ...] | None,
    contact: bool = False,
) -> dict[str, Any]:
    """The parameters of `_FILTERED`. `search` is a plain string: its LIKE characters are
    escaped here. `contact` keeps only the readers who asked to be contacted."""
    pattern = None
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
    return {
        **MASK_PARAMS,
        "survey": survey_id,
        "stored": list(stored) if stored is not None else None,
        "search": pattern,
        "group": list(group) if group is not None else None,
        "contact": contact,
        "scale": list(SCALE_KINDS),
        "text": list(TEXT_KINDS),
    }


def scale_kind(conn: psycopg.Connection, survey_id: UUID) -> str | None:
    """The kind of the survey's first scale question, None when it has none."""
    row = conn.execute(
        """select kind::text as kind from questions
           where survey_id = %s and kind::text = any(%s) order by position limit 1""",
        (survey_id, list(SCALE_KINDS)),
    ).fetchone()
    return row["kind"] if row else None


def responses(
    conn: psycopg.Connection,
    survey_id: UUID,
    stored: tuple[str, ...] | None,
    search: str | None,
    group: tuple[int, ...] | None,
    limit: int,
    offset: int,
    contact: bool = False,
) -> tuple[int, list[dict[str, Any]]]:
    """The matching responses, newest first, and how many match in all.

    `stored` limits to those stored segments (None for no limit), `search` looks in the
    masked comment, `group` keeps the main answers in it and `contact` only the
    readers who asked to be contacted."""
    params = _filter_params(survey_id, stored, search, group, contact)
    total = conn.execute(
        _FILTERED + "select count(*)::integer as n from filtered", params
    ).fetchone()["n"]
    rows = conn.execute(
        _FILTERED
        + """select id, submitted_at, segment, answer, reason, comment, was_masked,
                    contact_requested, contact_ref, contact_email
             from filtered order by submitted_at desc, id desc
             limit %(limit)s offset %(offset)s""",
        {**params, "limit": limit, "offset": offset},
    ).fetchall()
    return total, rows


def response_detail(
    conn: psycopg.Connection, survey_id: UUID, response_id: UUID
) -> dict[str, Any] | None:
    """One response with every question of its survey in order (text masked), or None."""
    response = conn.execute(
        """select id, submitted_at, segment, contact_requested, contact_ref, contact_email
           from responses where id = %s and survey_id = %s""",
        (response_id, survey_id),
    ).fetchone()
    if response is None:
        return None
    response["answers"] = conn.execute(
        f"""select q.id as question_id, q.prompt, q.kind::text as kind,
                   a.value_number, a.value_choices, a.value_text as raw_text,
                   {mask_sql("a.value_text")} as text
            from questions q
            left join answers a on a.question_id = q.id and a.response_id = %(response)s
            where q.survey_id = %(survey)s order by q.position""",
        {**MASK_PARAMS, "response": response_id, "survey": survey_id},
    ).fetchall()
    return response


def responses_export(
    conn: psycopg.Connection,
    survey_id: UUID,
    stored: tuple[str, ...] | None,
    search: str | None,
    group: tuple[int, ...] | None,
    contact: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The questions in order, and every matching response (newest first) with its masked
    answers in `answers`, a dict by question id."""
    questions = conn.execute(
        "select id, prompt from questions where survey_id = %s order by position", (survey_id,)
    ).fetchall()
    rows = conn.execute(
        _FILTERED
        + "select id, submitted_at, segment from filtered order by submitted_at desc, id desc",
        _filter_params(survey_id, stored, search, group, contact),
    ).fetchall()
    by_response: dict[UUID, dict[UUID, dict[str, Any]]] = {row["id"]: {} for row in rows}
    for answer in conn.execute(
        f"""select a.response_id, a.question_id, a.value_number, a.value_choices,
                   {mask_sql("a.value_text")} as text
            from answers a where a.response_id = any(%(ids)s)""",
        {**MASK_PARAMS, "ids": list(by_response)},
    ).fetchall():
        by_response[answer["response_id"]][answer["question_id"]] = answer
    for row in rows:
        row["answers"] = by_response[row["id"]]
    return questions, rows
