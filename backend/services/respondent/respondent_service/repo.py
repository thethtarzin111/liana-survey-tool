"""SQL for the answer path. Readers have no login: the survey's organisation is
found from its public token in survey_links, then the survey is read through
tenant_connection() with row-level security as everywhere else."""

from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from liana_survey_shared.config import get_settings
from liana_survey_shared.db import tenant_connection


def tenant_for_token(link_token: str) -> UUID | None:
    """The organisation a public link belongs to, or None for unknown links."""
    with psycopg.connect(get_settings().database_url) as conn:
        row = conn.execute(
            "select tenant_id from survey_links where link_token = %s", (link_token,)
        ).fetchone()
    return row[0] if row else None


def survey_for_token(tenant_id: UUID, link_token: str) -> dict[str, Any] | None:
    """What the answer page needs: status, thank-you message, colours and the main question."""
    with tenant_connection(tenant_id) as conn:
        conn.row_factory = dict_row
        survey = conn.execute(
            """select id, status, title, thank_you, accent_color, background_color
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
