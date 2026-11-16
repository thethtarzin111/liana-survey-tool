"""SQL for surveys. Every query runs on a tenant_db() connection, so
row-level security limits it to the current tenant; tenant_id is still
written explicitly on insert because the policy checks it."""

from typing import Any
from uuid import UUID

import psycopg

from .schemas import SurveyCreate, SurveyStatus, SurveyUpdate

COLUMNS = """id, title, type, status, anonymous, language, opens_at, closes_at,
    response_limit, created_at, updated_at"""


def create(
    conn: psycopg.Connection, tenant_id: UUID, user_id: UUID, data: SurveyCreate
) -> dict[str, Any]:
    row = conn.execute(
        f"""insert into surveys (tenant_id, title, type, status, created_by)
            values (%s, %s, %s, %s, %s)
            returning {COLUMNS}""",
        (tenant_id, data.title, data.type.value, SurveyStatus.draft.value, user_id),
    ).fetchone()
    assert row is not None
    return row


def list_all(conn: psycopg.Connection) -> list[dict[str, Any]]:
    return conn.execute(f"select {COLUMNS} from surveys order by updated_at desc, id").fetchall()


def get(conn: psycopg.Connection, survey_id: UUID) -> dict[str, Any] | None:
    return conn.execute(f"select {COLUMNS} from surveys where id = %s", (survey_id,)).fetchone()


def update(conn: psycopg.Connection, survey_id: UUID, data: SurveyUpdate) -> dict[str, Any] | None:
    changes = data.model_dump(mode="json", exclude_unset=True, exclude_none=True)
    if not changes:
        return get(conn, survey_id)
    # Column names come from the SurveyUpdate model, never from the request body.
    sets = ", ".join(f"{col} = %s" for col in changes)
    return conn.execute(
        f"update surveys set {sets}, updated_at = now() where id = %s returning {COLUMNS}",
        (*changes.values(), survey_id),
    ).fetchone()
