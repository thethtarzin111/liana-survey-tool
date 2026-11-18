"""Database access with tenant isolation.

Every table has a tenant_id column protected by row-level security (see
backend/db/migrations). Always open connections through tenant_connection(), which
sets app.tenant_id for the current transaction. Without it, queries return
no rows.

There are two exceptions:
- tenant_for_link(): a reader opening an answer link has no login, so the
  survey's organisation is looked up from the link first.
- due_response_digests(): the worker's sweep for "new responses" emails looks
  across all organisations for surveys whose email is due.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import psycopg

from .config import get_settings


@contextmanager
def tenant_connection(
    tenant_id: UUID, database_url: str | None = None
) -> Iterator[psycopg.Connection]:
    url = database_url or get_settings().database_url
    with psycopg.connect(url) as conn, conn.transaction():
        conn.execute("select set_config('app.tenant_id', %s, true)", (str(tenant_id),))
        yield conn


def tenant_for_link(link_token: str, database_url: str | None = None) -> UUID | None:
    """The organisation a public survey link belongs to, or None for unknown links.

    The only query that runs before the tenant is known. It reads survey_links,
    whose policy lets anyone look up a token (lookup_by_token); every other table
    still returns no rows on this connection. Everything after it goes through
    tenant_connection().
    """
    url = database_url or get_settings().database_url
    with psycopg.connect(url) as conn:
        row = conn.execute(
            "select tenant_id from survey_links where link_token = %s", (link_token,)
        ).fetchone()
    return row[0] if row else None


def due_response_digests(
    interval_seconds: int, database_url: str | None = None
) -> list[tuple[UUID, UUID]]:
    """(survey id, tenant id) of every survey whose "new responses" email is due:
    notify_on_response is on, responses arrived since the last email, and the
    last email went out at least `interval_seconds` ago.

    Reads through the due_response_digests() SQL function, which returns ids
    only. Everything after it (reading the survey, claiming the email) goes
    through tenant_connection().
    """
    url = database_url or get_settings().database_url
    with psycopg.connect(url) as conn:
        rows = conn.execute(
            "select survey_id, tenant_id from due_response_digests(%s)", (interval_seconds,)
        ).fetchall()
    return [(row[0], row[1]) for row in rows]


def ping(database_url: str | None = None) -> bool:
    """Return True if the database answers. Used by readiness checks."""
    try:
        with psycopg.connect(
            database_url or get_settings().database_url, connect_timeout=2
        ) as conn:
            conn.execute("select 1")
        return True
    except psycopg.Error:
        return False
