"""SQL for templates. Row-level security shows built-in templates (tenant_id null)
plus the organisation's own ones."""

from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from ..surveys.repo import COLUMNS as SURVEY_COLUMNS
from ..surveys.schemas import SurveyStatus, SurveyType

COLUMNS = "id, name, type, description, thank_you, featured, questions"


def list_all(conn: psycopg.Connection, survey_type: SurveyType | None) -> list[dict[str, Any]]:
    if survey_type is None:
        return conn.execute(f"select {COLUMNS} from templates order by sort_order, name").fetchall()
    return conn.execute(
        f"select {COLUMNS} from templates where type = %s order by sort_order, name",
        (survey_type.value,),
    ).fetchall()


def get(conn: psycopg.Connection, template_id: UUID) -> dict[str, Any] | None:
    return conn.execute(f"select {COLUMNS} from templates where id = %s", (template_id,)).fetchone()


def create_survey(
    conn: psycopg.Connection,
    tenant_id: UUID,
    user_id: UUID,
    template: dict[str, Any],
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a draft survey with the template's name, type, thank-you message and questions."""
    survey = conn.execute(
        f"""insert into surveys (tenant_id, title, thank_you, type, status, created_by)
            values (%s, %s, %s, %s, %s, %s)
            returning {SURVEY_COLUMNS}""",
        (
            tenant_id,
            template["name"],
            template["thank_you"] or None,
            template["type"],
            SurveyStatus.draft.value,
            user_id,
        ),
    ).fetchone()
    assert survey is not None
    for position, question in enumerate(questions, start=1):
        conn.execute(
            """insert into questions
                 (tenant_id, survey_id, position, kind, prompt, options, required)
               values (%s, %s, %s, %s, %s, %s, %s)""",
            (
                tenant_id,
                survey["id"],
                position,
                question["kind"],
                question["prompt"],
                Jsonb(question["options"]),
                question["required"],
            ),
        )
    return survey
