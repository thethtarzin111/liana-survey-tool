from typing import Any
from uuid import UUID

import psycopg


def response_feed(conn: psycopg.Connection) -> list[dict]:
    return conn.execute(
        """select r.id, r.survey_id, s.title as survey, r.segment, r.submitted_at,
                  main.value_number as answer,
                  (select string_agg(a.value_text, E'\\n' order by q.position)
                   from answers a join questions q on q.id = a.question_id
                   where a.response_id = r.id and nullif(trim(a.value_text), '') is not null
                  ) as comment
           from responses r join surveys s on s.id = r.survey_id
           left join lateral (
             select a.value_number from questions q
             left join answers a on a.question_id = q.id and a.response_id = r.id
             where q.survey_id = s.id order by q.position limit 1
           ) main on true
           order by r.submitted_at desc, r.id limit 500"""
    ).fetchall()


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


def survey_result(conn: psycopg.Connection, survey_id: UUID, segment: str) -> dict[str, Any] | None:
    survey = conn.execute(
        """select s.id, s.title, s.type, s.status, q.id as main_question_id
           from surveys s left join lateral (
             select id from questions where survey_id = s.id order by position limit 1
           ) q on true where s.id = %s""",
        (survey_id,),
    ).fetchone()
    if survey is None:
        return None
    params: list[Any] = [survey_id]
    segment_sql = ""
    if segment != "all":
        segment_sql = "and r.segment = %s"
        params.append(segment)
    rows = (
        conn.execute(
            f"""select a.value_number, count(*)::integer as count
                from responses r join answers a on a.response_id = r.id
                where r.survey_id = %s and a.question_id = %s {segment_sql}
                      and a.value_number is not null
                group by a.value_number""",
            (survey_id, survey["main_question_id"], *params[1:]),
        ).fetchall()
        if survey["main_question_id"]
        else []
    )
    response_count = conn.execute(
        f"select count(*)::integer as count from responses r where r.survey_id = %s {segment_sql}",
        params,
    ).fetchone()["count"]
    segments = [
        row["segment"]
        for row in conn.execute(
            "select distinct segment from responses where survey_id = %s order by segment",
            (survey_id,),
        ).fetchall()
        if row["segment"] != "all"
    ]
    return {
        **survey,
        "answers": response_count,
        "distribution": {str(int(row["value_number"])): row["count"] for row in rows},
        "segments": segments,
        "questions": question_charts(conn, survey_id, segment),
        "comments": comments(conn, survey_id, segment),
    }


def question_charts(conn: psycopg.Connection, survey_id: UUID, segment: str) -> list[dict]:
    questions = conn.execute(
        "select id, prompt, kind, options from questions where survey_id = %s order by position",
        (survey_id,),
    ).fetchall()
    charts = []
    for question in questions:
        kind = question["kind"]
        scales = {"thumbs": range(3), "nps": range(11), "rating": range(1, 6)}
        if kind not in scales and kind not in {
            "single_choice",
            "multiple_choice",
            "dropdown",
            "reasons",
        }:
            continue
        answers = conn.execute(
            """select a.value_number, a.value_choices from answers a
               join responses r on r.id = a.response_id
               where a.question_id = %s and (%s = 'all' or r.segment = %s)""",
            (question["id"], segment, segment),
        ).fetchall()
        labels = [str(value) for value in scales[kind]] if kind in scales else question["options"]
        counts = dict.fromkeys(labels, 0)
        for answer in answers:
            values = (
                [str(int(answer["value_number"]))]
                if answer["value_number"] is not None
                else answer["value_choices"] or []
            )
            for value in set(values):
                if value in counts:
                    counts[value] += 1
        charts.append(
            {
                "id": str(question["id"]),
                "kind": kind,
                "prompt": question["prompt"],
                "answers": len(answers),
                "options": [{"label": label, "count": count} for label, count in counts.items()],
            }
        )
    return charts


def comments(conn: psycopg.Connection, survey_id: UUID, segment: str) -> list[dict]:
    return conn.execute(
        """select a.id, a.value_text as comment, r.segment, r.submitted_at,
                  (select value_number from answers main_answer
                   join questions q on q.id = main_answer.question_id
                   where main_answer.response_id = r.id
                   order by q.position limit 1) as answer
           from answers a join responses r on r.id = a.response_id
           where r.survey_id = %s and (%s = 'all' or r.segment = %s)
             and nullif(trim(a.value_text), '') is not null
           order by r.submitted_at desc, a.id limit 100""",
        (survey_id, segment, segment),
    ).fetchall()
