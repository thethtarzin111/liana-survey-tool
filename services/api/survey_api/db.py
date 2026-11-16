"""FastAPI dependency for a tenant-scoped database connection.

Every request that touches the database uses tenant_db(). It opens a
connection with app.tenant_id set to the signed-in user's tenant, so
row-level security hides every other tenant's rows. The transaction
commits when the request handler returns and rolls back on an error.
"""

from collections.abc import Iterator

import psycopg
from fastapi import Depends
from psycopg.rows import dict_row

from liana_survey_shared.db import tenant_connection

from .auth.dev_stub import CurrentUser, current_user


def tenant_db(user: CurrentUser = Depends(current_user)) -> Iterator[psycopg.Connection]:
    with tenant_connection(user.tenant_id) as conn:
        conn.row_factory = dict_row
        yield conn
