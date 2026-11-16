"""Tenant-safe SQL operations for survey questions."""

from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from .schemas import QuestionCreate, QuestionUpdate

COLUMNS = "id, survey_id, position, kind, prompt, options, required"


def lock_survey(conn: psycopg.Connection, survey_id: UUID) -> bool:
    """Serialize position changes and confirm the tenant can see the survey."""
    return (
        conn.execute("select id from surveys where id = %s for update", (survey_id,)).fetchone()
        is not None
    )


def list_all(conn: psycopg.Connection, survey_id: UUID) -> list[dict[str, Any]]:
    return conn.execute(
        f"select {COLUMNS} from questions where survey_id = %s order by position",
        (survey_id,),
    ).fetchall()


def create(
    conn: psycopg.Connection, tenant_id: UUID, survey_id: UUID, data: QuestionCreate
) -> dict[str, Any]:
    position = conn.execute(
        """select coalesce(max(position), 0) + 1 as next_position
           from questions where survey_id = %s""",
        (survey_id,),
    ).fetchone()["next_position"]
    row = conn.execute(
        f"""insert into questions
            (tenant_id, survey_id, position, kind, prompt, options, required)
            values (%s, %s, %s, %s, %s, %s, %s)
            returning {COLUMNS}""",
        (
            tenant_id,
            survey_id,
            position,
            data.kind.value,
            data.prompt,
            Jsonb(data.options),
            data.required,
        ),
    ).fetchone()
    assert row is not None
    return row


def update(
    conn: psycopg.Connection, survey_id: UUID, question_id: UUID, data: QuestionUpdate
) -> dict[str, Any] | None:
    changes = data.model_dump(mode="json", exclude_unset=True)
    if not changes:
        return conn.execute(
            f"select {COLUMNS} from questions where survey_id = %s and id = %s",
            (survey_id, question_id),
        ).fetchone()
    if "options" in changes:
        changes["options"] = Jsonb(changes["options"])
    sets = ", ".join(f"{column} = %s" for column in changes)
    return conn.execute(
        f"""update questions set {sets}
            where survey_id = %s and id = %s returning {COLUMNS}""",
        (*changes.values(), survey_id, question_id),
    ).fetchone()


def delete(conn: psycopg.Connection, survey_id: UUID, question_id: UUID) -> bool:
    deleted = conn.execute(
        "delete from questions where survey_id = %s and id = %s returning position",
        (survey_id, question_id),
    ).fetchone()
    if deleted is None:
        return False
    conn.execute(
        "update questions set position = position - 1 where survey_id = %s and position > %s",
        (survey_id, deleted["position"]),
    )
    return True


def duplicate(
    conn: psycopg.Connection, tenant_id: UUID, survey_id: UUID, question_id: UUID
) -> dict[str, Any] | None:
    original = conn.execute(
        """select position, kind, prompt, options, required from questions
           where survey_id = %s and id = %s""",
        (survey_id, question_id),
    ).fetchone()
    if original is None:
        return None
    position = original["position"]
    # Move later questions through a disjoint range to avoid the immediate
    # unique (survey_id, position) constraint colliding during the update.
    conn.execute(
        "update questions set position = position + 1000000 where survey_id = %s and position > %s",
        (survey_id, position),
    )
    conn.execute(
        """update questions set position = position - 999999
           where survey_id = %s and position > 1000000""",
        (survey_id,),
    )
    return conn.execute(
        f"""insert into questions
            (tenant_id, survey_id, position, kind, prompt, options, required)
            values (%s, %s, %s, %s, %s, %s, %s)
            returning {COLUMNS}""",
        (
            tenant_id,
            survey_id,
            position + 1,
            original["kind"],
            original["prompt"],
            Jsonb(original["options"]),
            original["required"],
        ),
    ).fetchone()


def reorder(conn: psycopg.Connection, survey_id: UUID, question_ids: list[UUID]) -> bool:
    current = conn.execute(
        "select id from questions where survey_id = %s order by position", (survey_id,)
    ).fetchall()
    if {row["id"] for row in current} != set(question_ids) or len(current) != len(question_ids):
        return False
    if not question_ids:
        return True
    conn.execute(
        """update questions as question
           set position = -ordered.position
           from (
             select item.id, item.ordinality::integer as position
             from unnest(%s::uuid[]) with ordinality as item(id, ordinality)
           ) as ordered
           where question.id = ordered.id and question.survey_id = %s""",
        (question_ids, survey_id),
    )
    conn.execute("update questions set position = -position where survey_id = %s", (survey_id,))
    return True
