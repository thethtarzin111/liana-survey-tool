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
    """What the answer page needs: status, language, thank-you message, colours, the main
    question, whether unsigned newsletter links are accepted, and the close date,
    response limit and response count (#47)."""
    with tenant_connection(tenant_id) as conn:
        conn.row_factory = dict_row
        survey = conn.execute(
            """select s.id, s.status, s.title, s.language, s.thank_you,
                      s.accent_color, s.background_color,
                      s.newsletter_links, s.closes_at, s.response_limit,
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


def answered_before(tenant_id: UUID, survey_id: UUID, response_key: str) -> bool:
    """Whether this reader (by the key derived from their link) has a saved answer."""
    with tenant_connection(tenant_id) as conn:
        row = conn.execute(
            "select 1 from responses where survey_id = %s and link_token_hash = %s",
            (survey_id, response_key),
        ).fetchone()
    return row is not None
