from typing import Any
from uuid import UUID

import psycopg


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
