from typing import Any
from uuid import UUID

import psycopg

from ..repo import SCALE_KINDS, TEXT_KINDS


def comment_rows(
    conn: psycopg.Connection, survey_id: UUID, stored: tuple[str, ...] | None
) -> dict[str, Any] | None:
    """The survey's main scale kind, its reasons (existing themes), and every comment (the
    first text question's answer, else the "Tell us more" box) with that response's main
    answer, oldest first. `stored` limits to those stored segments, None for all. None
    when the survey is not found."""
    if conn.execute("select 1 from surveys where id = %s", (survey_id,)).fetchone() is None:
        return None
    picked = conn.execute(
        """select
             (select kind::text from questions where survey_id = %(survey)s
              and kind::text = any(%(scale)s) order by position limit 1) as kind,
             (select options from questions where survey_id = %(survey)s
              and kind::text = 'reasons' order by position limit 1) as reasons""",
        {"survey": survey_id, "scale": list(SCALE_KINDS)},
    ).fetchone()
    rows = conn.execute(
        """with q as (
             select
               (select id from questions where survey_id = %(survey)s
                and kind::text = any(%(scale)s) order by position limit 1) as scale,
               (select id from questions where survey_id = %(survey)s
                and kind::text = any(%(text)s) order by position limit 1) as comment
           )
           select * from (
             select
               -- The survey's own text question, else the "Tell us more" box
               -- (responses.comment), as the Responses tab shows it.
               coalesce((select c.value_text from answers c
                         where c.response_id = r.id and c.question_id = q.comment limit 1),
                        r.comment) as text,
               (select a.value_number::integer from answers a
                where a.response_id = r.id and a.question_id = q.scale limit 1) as answer,
               r.submitted_at, r.id
             from responses r
             cross join q
             where r.survey_id = %(survey)s
               and (%(stored)s::text[] is null or r.segment = any(%(stored)s))
           ) with_text
           where text is not null
           order by submitted_at, id""",
        {
            "survey": survey_id,
            "scale": list(SCALE_KINDS),
            "text": list(TEXT_KINDS),
            "stored": list(stored) if stored is not None else None,
        },
    ).fetchall()
    return {"kind": picked["kind"], "reasons": list(picked["reasons"] or []), "rows": rows}
