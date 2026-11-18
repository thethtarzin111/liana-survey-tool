from typing import Any
from uuid import UUID

import psycopg


def response_feed(
    conn: psycopg.Connection,
    survey_id: UUID | None = None,
    segment: str = "all",
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
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
           where (%s::uuid is null or r.survey_id = %s)
             and (%s = 'all' or r.segment = %s)
           order by r.submitted_at desc, r.id limit %s offset %s""",
        (survey_id, survey_id, segment, segment, limit, offset),
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
