"""SQL for templates. Row-level security shows built-in templates (tenant_id null)
plus the organisation's own ones, and lets it change only its own."""

from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from ..surveys.repo import COLUMNS as SURVEY_COLUMNS
from ..surveys.schemas import SurveyStatus, SurveyType
from .schemas import TemplateUpdate

COLUMNS = (
    "id, name, type, description, thank_you, featured, tenant_id is not null as own, questions,"
    " accent_color, background_color"
)
# Built-in templates in their set order, then the organisation's own by name.
ORDER = "order by tenant_id is not null, sort_order, name"


def list_all(conn: psycopg.Connection, survey_type: SurveyType | None) -> list[dict[str, Any]]:
    if survey_type is None:
        return conn.execute(f"select {COLUMNS} from templates {ORDER}").fetchall()
    return conn.execute(
        f"select {COLUMNS} from templates where type = %s {ORDER}",
        (survey_type.value,),
    ).fetchall()


def get(conn: psycopg.Connection, template_id: UUID) -> dict[str, Any] | None:
    return conn.execute(f"select {COLUMNS} from templates where id = %s", (template_id,)).fetchone()


def create(
    conn: psycopg.Connection,
    tenant_id: UUID,
    name: str,
    description: str,
    survey: dict[str, Any],
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Save a survey's type, thank-you message, branding colours and questions as the
    organisation's template."""
    row = conn.execute(
        f"""insert into templates
              (tenant_id, name, type, description, thank_you, questions,
               accent_color, background_color)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            returning {COLUMNS}""",
        (
            tenant_id,
            name,
            survey["type"],
            description,
            survey["thank_you"] or "",
            Jsonb(questions),
            survey["accent_color"],
            survey["background_color"],
        ),
    ).fetchone()
    assert row is not None
    return row


def update(
    conn: psycopg.Connection, template_id: UUID, data: TemplateUpdate
) -> dict[str, Any] | None:
    """Rename one of the organisation's own templates or change its description."""
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return get(conn, template_id)
    # Column names come from the TemplateUpdate model, never from the request body.
    sets = ", ".join(f"{col} = %s" for col in changes)
    return conn.execute(
        f"""update templates set {sets}
            where id = %s and tenant_id is not null
            returning {COLUMNS}""",
        (*changes.values(), template_id),
    ).fetchone()


def delete(conn: psycopg.Connection, template_id: UUID) -> bool:
    """Delete one of the organisation's own templates. Surveys made from it stay."""
    cur = conn.execute(
        "delete from templates where id = %s and tenant_id is not null", (template_id,)
    )
    return cur.rowcount > 0


def create_survey(
    conn: psycopg.Connection,
    tenant_id: UUID,
    user_id: UUID,
    template: dict[str, Any],
    questions: list[dict[str, Any]],
    colours: tuple[str, str],
) -> dict[str, Any]:
    """Create a draft survey with the template's name, type, thank-you message and
    questions, and the given accent and background colours."""
    survey = conn.execute(
        f"""insert into surveys
              (tenant_id, title, thank_you, type, status, created_by,
               accent_color, background_color)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            returning {SURVEY_COLUMNS}""",
        (
            tenant_id,
            template["name"],
            template["thank_you"] or None,
            template["type"],
            SurveyStatus.draft.value,
            user_id,
            *colours,
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
