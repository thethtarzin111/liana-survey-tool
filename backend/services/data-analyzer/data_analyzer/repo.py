from typing import Any

import psycopg


def performance_rows(conn: psycopg.Connection) -> list[dict[str, Any]]:
    """Views, responses and the main question's answer counts per survey and channel.

    `distribution` only counts the answers that came through that channel, so each
    row's main result is the channel's own."""
    return conn.execute(
        """select s.id as survey_id, s.title as survey, s.type,
                  channels.channel::text as channel,
                  coalesce(v.view_count, 0) as views,
                  coalesce(r.responses, 0) as responses,
                  coalesce(d.distribution, '{}'::jsonb) as distribution
           from surveys s
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
           order by s.updated_at desc, s.id, channels.channel"""
    ).fetchall()
