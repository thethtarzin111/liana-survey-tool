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
    """What the answer page needs: status, thank-you message, colours, the main
    question and whether unsigned newsletter links are accepted."""
    with tenant_connection(tenant_id) as conn:
        conn.row_factory = dict_row
        survey = conn.execute(
            """select id, status, title, thank_you, accent_color, background_color,
                      newsletter_links
               from surveys where link_token = %s""",
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
