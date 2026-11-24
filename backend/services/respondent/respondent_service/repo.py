"""SQL for the answer path. Readers have no login: the survey's organisation is
found from its public token with the shared tenant_for_link(), then the survey is
read through tenant_connection() with row-level security as everywhere else."""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from liana_survey_shared.db import tenant_connection, tenant_for_link


def tenant_for_token(link_token: str) -> UUID | None:
    """The organisation a public link belongs to, or None for unknown links."""
    return tenant_for_link(link_token)


def survey_for_token(tenant_id: UUID, link_token: str) -> dict[str, Any] | None:
    """What the answer pages need: status, type, language, the texts readers see
    (title, description, thank-you message), colours, the main question, whether
    unsigned newsletter links are accepted, the close date, response limit and
    response count (#47), and the reader options: the "Tell us more" box, the
    "Contact me" opt-in and whether answers are identified (anonymous off)."""
    with tenant_connection(tenant_id) as conn:
        conn.row_factory = dict_row
        survey = conn.execute(
            """select s.id, s.status, s.type::text as type, s.title, s.reader_title, s.description,
                      s.language, s.thank_you,
                      s.accent_color, s.background_color,
                      s.newsletter_links, s.closes_at, s.response_limit,
                      s.comment_field, s.contact_opt_in, s.anonymous,
                      coalesce(a.response_count, 0) as response_count
               from surveys s left join survey_aggregates a on a.survey_id = s.id
               where s.link_token = %s""",
            (link_token,),
        ).fetchone()
        if survey is None:
            return None
        main = conn.execute(
            "select id, kind from questions where survey_id = %s order by position limit 1",
            (survey["id"],),
        ).fetchone()
    return {
        **survey,
        "main_id": main["id"] if main else None,
        "main_kind": main["kind"] if main else None,
    }


def questions(tenant_id: UUID, survey_id: UUID) -> list[dict[str, Any]]:
    """The survey's questions in order, for the survey link page (#105)."""
    with tenant_connection(tenant_id) as conn:
        conn.row_factory = dict_row
        return conn.execute(
            """select id, kind::text as kind, prompt, options, required from questions
               where survey_id = %s order by position""",
            (survey_id,),
        ).fetchall()


def record_view(tenant_id: UUID, survey_id: UUID, channel: str) -> None:
    """Count a valid visit. The row is kept per survey/channel for fast reports."""
    with tenant_connection(tenant_id) as conn:
        conn.execute(
            """insert into survey_channel_views (survey_id, tenant_id, channel, view_count)
               values (%s, %s, %s, 1)
               on conflict (survey_id, channel) do update set
                 view_count = survey_channel_views.view_count + 1, updated_at = now()""",
            (survey_id, tenant_id, channel),
        )


def answered_before(tenant_id: UUID, survey_id: UUID, response_key: str) -> bool:
    """Whether this reader (by the key derived from their link) has a saved answer."""
    with tenant_connection(tenant_id) as conn:
        row = conn.execute(
            "select 1 from responses where survey_id = %s and link_token_hash = %s",
            (survey_id, response_key),
        ).fetchone()
    return row is not None
