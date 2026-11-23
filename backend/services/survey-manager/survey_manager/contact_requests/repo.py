"""SQL for contact requests. Every call runs on a tenant connection."""

from uuid import UUID

import psycopg

from .domain import Status

# One contact request with its survey and the reader's answer: the first scale
# question's value and the first reasons question's choices (as on Results).
# The respondent is shown by their LianaMailer contact reference only.
_SELECT = """
select c.id, c.survey_id, s.title as survey_title, s.type::text as survey_type, c.contact_ref,
  (select a.value_number::integer
   from answers a join questions q on q.id = a.question_id
   where a.response_id = c.response_id and q.kind::text in ('nps', 'rating', 'thumbs')
   order by q.position limit 1) as answer,
  (select case when a.value_choices is not null
               then (select string_agg(ch.value, '; ' order by ch.ord)
                     from jsonb_array_elements_text(a.value_choices)
                          with ordinality ch(value, ord))
               else a.value_text end
   from answers a join questions q on q.id = a.question_id
   where a.response_id = c.response_id and q.kind::text = 'reasons'
   order by q.position limit 1) as reason,
  r.segment, c.status::text as status, c.liana_status, c.created_at
from contact_requests c
join surveys s on s.id = c.survey_id
join responses r on r.id = c.response_id
"""


def list_all(conn: psycopg.Connection, status: Status | None, survey_id: UUID | None) -> list[dict]:
    """Newest first."""
    return conn.execute(
        _SELECT
        + """where (%(status)s::text is null or c.status::text = %(status)s)
               and (%(survey)s::uuid is null or c.survey_id = %(survey)s)
             order by c.created_at desc, c.id""",
        {"status": status, "survey": survey_id},
    ).fetchall()


def status_counts(conn: psycopg.Connection, survey_id: UUID | None) -> list[tuple[str, int]]:
    rows = conn.execute(
        """select status::text as status, count(*)::integer as n from contact_requests
           where (%(survey)s::uuid is null or survey_id = %(survey)s)
           group by status""",
        {"survey": survey_id},
    ).fetchall()
    return [(row["status"], row["n"]) for row in rows]


def get(conn: psycopg.Connection, request_id: UUID) -> dict | None:
    return conn.execute(_SELECT + "where c.id = %s", (request_id,)).fetchone()


def set_status(conn: psycopg.Connection, request_id: UUID, status: Status) -> bool:
    """False when there is no such request (or it belongs to another tenant)."""
    return (
        conn.execute(
            "update contact_requests set status = %s::contact_request_status where id = %s",
            (status, request_id),
        ).rowcount
        == 1
    )
