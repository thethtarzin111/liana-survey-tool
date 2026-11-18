from typing import Any
from uuid import UUID

import psycopg


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
    }
