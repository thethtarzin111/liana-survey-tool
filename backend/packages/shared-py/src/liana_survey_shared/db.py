"""Database access with tenant isolation.

Every table has a tenant_id column protected by row-level security (see
backend/db/migrations). Always open connections through tenant_connection(), which
sets app.tenant_id for the current transaction. Without it, queries return
no rows.
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
