"""FastAPI dependency for tenant-scoped database access.

Use it like this, so the transaction commits *before* the response is sent:

    def create_survey(..., db: TenantDB = Depends(tenant_db)):
        with db() as conn:
            return repo.create(conn, ...)

Why not yield a connection from the dependency? FastAPI runs the code after
`yield` once the response has already gone out. A client that reads right
after a write (create, then open) could then get there before the commit and
see 404. Committing inside the handler avoids that race.

The connection has app.tenant_id set to the signed-in user's tenant, so
row-level security hides every other tenant's rows. The transaction commits
when the `with` block ends and rolls back on an error.
"""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

import psycopg
from fastapi import Depends
from psycopg.rows import dict_row

from ..db import tenant_connection
from .auth import CurrentUser, current_user

TenantDB = Callable[[], AbstractContextManager[psycopg.Connection]]


def tenant_db(user: CurrentUser = Depends(current_user)) -> TenantDB:
    @contextmanager
    def connect() -> Iterator[psycopg.Connection]:
        with tenant_connection(user.tenant_id) as conn:
            conn.row_factory = dict_row
            yield conn

    return connect
