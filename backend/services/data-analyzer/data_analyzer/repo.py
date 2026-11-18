from typing import Any

import psycopg


def performance_rows(conn: psycopg.Connection) -> list[dict[str, Any]]:
    return conn.execute(
        """select s.id as survey_id, s.title as survey, s.type,
                  channels.channel::text as channel,
                  coalesce(v.view_count, 0) as views,
                  coalesce(r.responses, 0) as responses,
                  coalesce(a.distribution, '{}'::jsonb) as distribution
           from surveys s
           cross join unnest(enum_range(null::distribution_channel)) channels(channel)
           left join survey_channel_views v
             on v.survey_id = s.id and v.channel = channels.channel
           left join (
             select survey_id, channel, count(*)::integer as responses
             from responses group by survey_id, channel
           ) r on r.survey_id = s.id and r.channel = channels.channel
           left join survey_aggregates a on a.survey_id = s.id
           where coalesce(v.view_count, 0) > 0 or coalesce(r.responses, 0) > 0
           order by s.updated_at desc, s.id, channels.channel"""
    ).fetchall()
