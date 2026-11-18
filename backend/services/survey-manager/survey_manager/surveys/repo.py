"""SQL for surveys. Every query runs on a tenant_db() connection, so
row-level security limits it to the current tenant; tenant_id is still
written explicitly on insert because the policy checks it."""

from typing import Any
from uuid import UUID

import psycopg

from .schemas import SurveyCreate, SurveyStatus, SurveyUpdate

COLUMN_NAMES = (
    "id",
    "title",
    "description",
    "thank_you",
    "comment_field",
    "show_results",
    "contact_opt_in",
    "accent_color",
    "background_color",
    "logo_updated_at",
    "link_token",
    "published_at",
    "newsletter_links",
    "type",
    "status",
    "anonymous",
    "language",
    "opens_at",
    "closes_at",
    "response_limit",
    "notify_on_response",
    "created_at",
    "updated_at",
)
COLUMNS = ", ".join(COLUMN_NAMES)
# The same columns qualified with the surveys alias, for queries with joins.
S_COLUMNS = ", ".join(f"s.{name}" for name in COLUMN_NAMES)


def create(
    conn: psycopg.Connection, tenant_id: UUID, user_id: UUID, data: SurveyCreate
) -> dict[str, Any]:
    row = conn.execute(
        f"""insert into surveys (tenant_id, title, description, type, status, created_by)
            values (%s, %s, %s, %s, %s, %s)
            returning {COLUMNS}""",
        (
            tenant_id,
            data.title,
            data.description,
            data.type.value,
            SurveyStatus.draft.value,
            user_id,
        ),
    ).fetchone()
    assert row is not None
    return row


def list_all(
    conn: psycopg.Connection, search: str | None = None, status: SurveyStatus | None = None
) -> list[dict[str, Any]]:
    """Surveys with their answer counts, most recently changed first.

    `search` matches anywhere in the title, ignoring case."""
    where: list[str] = []
    params: list[Any] = []
    if search:
        where.append("s.title ilike %s")
        params.append(f"%{escape_like(search)}%")
    if status is not None:
        where.append("s.status = %s")
        params.append(status.value)
    clause = f"where {' and '.join(where)}" if where else ""
    return conn.execute(
        f"""select {S_COLUMNS}, coalesce(a.response_count, 0) as answers,
                   coalesce(a.distribution, '{{}}'::jsonb) as distribution
            from surveys s left join survey_aggregates a on a.survey_id = s.id
            {clause}
            order by s.updated_at desc, s.id""",
        params,
    ).fetchall()


def escape_like(text: str) -> str:
    r"""Make %, _ and \ in user input match literally in an ILIKE pattern."""
    return text.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def get(conn: psycopg.Connection, survey_id: UUID) -> dict[str, Any] | None:
    return conn.execute(f"select {COLUMNS} from surveys where id = %s", (survey_id,)).fetchone()


def get_for_update(conn: psycopg.Connection, survey_id: UUID) -> dict[str, Any] | None:
    """Like get(), but locks the row until the transaction ends, so two status
    changes to the same survey cannot both pass the status check."""
    return conn.execute(
        f"select {COLUMNS} from surveys where id = %s for update", (survey_id,)
    ).fetchone()


def set_status(conn: psycopg.Connection, survey_id: UUID, status: SurveyStatus) -> dict[str, Any]:
    row = conn.execute(
        f"""update surveys set status = %s, updated_at = now() where id = %s
            returning {COLUMNS}""",
        (status.value, survey_id),
    ).fetchone()
    assert row is not None
    return row


def question_texts(conn: psycopg.Connection, survey_id: UUID) -> list[tuple[str, str]]:
    """(kind, prompt) of each question, in order: what publishing checks."""
    rows = conn.execute(
        "select kind, prompt from questions where survey_id = %s order by position", (survey_id,)
    ).fetchall()
    return [(row["kind"], row["prompt"]) for row in rows]


def main_question(conn: psycopg.Connection, survey_id: UUID) -> dict[str, Any] | None:
    """The first question (kind and prompt): the main question of template surveys."""
    return conn.execute(
        "select kind, prompt from questions where survey_id = %s order by position limit 1",
        (survey_id,),
    ).fetchone()


def allow_newsletter_links(conn: psycopg.Connection, survey_id: UUID) -> None:
    """From now on the survey accepts unsigned newsletter snippet links (#40)."""
    conn.execute("update surveys set newsletter_links = true where id = %s", (survey_id,))


def publish(conn: psycopg.Connection, survey_id: UUID, link_token: str) -> dict[str, Any]:
    """Make the survey live. Its link token is set once and then kept."""
    row = conn.execute(
        f"""update surveys
            set status = 'live', link_token = coalesce(link_token, %s),
                published_at = now(), updated_at = now()
            where id = %s returning {COLUMNS}""",
        (link_token, survey_id),
    ).fetchone()
    assert row is not None
    # The respondent service finds the survey's organisation from its link (#42).
    conn.execute(
        """insert into survey_links (link_token, survey_id, tenant_id)
           select link_token, id, tenant_id from surveys where id = %s
           on conflict do nothing""",
        (survey_id,),
    )
    return row


def duplicate(
    conn: psycopg.Connection, tenant_id: UUID, user_id: UUID, survey_id: UUID, title: str
) -> dict[str, Any] | None:
    """Copy a survey and its questions into a new draft with no dates set.

    Responses, contact requests and totals belong to the original and are not copied."""
    row = conn.execute(
        f"""insert into surveys
              (tenant_id, title, description, thank_you, type, status, anonymous, language,
               response_limit, notify_on_response, comment_field, show_results, contact_opt_in,
               accent_color, background_color, logo_updated_at, created_by)
            select %s, %s, description, thank_you, type, %s, anonymous, language,
                   response_limit, notify_on_response, comment_field, show_results, contact_opt_in,
                   accent_color, background_color, logo_updated_at, %s
            from surveys where id = %s
            returning {COLUMNS}""",
        (tenant_id, title, SurveyStatus.draft.value, user_id, survey_id),
    ).fetchone()
    if row is None:
        return None
    conn.execute(
        """insert into questions (tenant_id, survey_id, position, kind, prompt, options, required)
           select %s, %s, position, kind, prompt, options, required
           from questions where survey_id = %s""",
        (tenant_id, row["id"], survey_id),
    )
    conn.execute(
        """insert into survey_logos (survey_id, tenant_id, content_type, data)
           select %s, %s, content_type, data from survey_logos where survey_id = %s""",
        (row["id"], tenant_id, survey_id),
    )
    return row


def delete(conn: psycopg.Connection, survey_id: UUID) -> bool:
    """Delete a survey. Its questions, responses and answers go with it (on delete cascade)."""
    return conn.execute("delete from surveys where id = %s", (survey_id,)).rowcount == 1


def update(conn: psycopg.Connection, survey_id: UUID, data: SurveyUpdate) -> dict[str, Any] | None:
    # Explicitly empty descriptions are normalized to None and must be written
    # so that PATCH can clear a previously saved description.
    changes = data.model_dump(mode="json", exclude_unset=True)
    if not changes:
        return get(conn, survey_id)
    # Column names come from the SurveyUpdate model, never from the request body.
    sets = ", ".join(f"{col} = %s" for col in changes)
    return conn.execute(
        f"update surveys set {sets}, updated_at = now() where id = %s returning {COLUMNS}",
        (*changes.values(), survey_id),
    ).fetchone()


# --- Logo ---------------------------------------------------------------------


def put_logo(
    conn: psycopg.Connection, tenant_id: UUID, survey_id: UUID, content_type: str, data: bytes
) -> dict[str, Any] | None:
    """Save (or replace) the survey's logo. Returns the survey, or None if there is none."""
    survey = conn.execute(
        f"""update surveys set logo_updated_at = now(), updated_at = now()
            where id = %s returning {COLUMNS}""",
        (survey_id,),
    ).fetchone()
    if survey is None:
        return None
    conn.execute(
        """insert into survey_logos (survey_id, tenant_id, content_type, data)
           values (%s, %s, %s, %s)
           on conflict (survey_id) do update
             set content_type = excluded.content_type, data = excluded.data, updated_at = now()""",
        (survey_id, tenant_id, content_type, data),
    )
    return survey


def get_logo(conn: psycopg.Connection, survey_id: UUID) -> dict[str, Any] | None:
    return conn.execute(
        "select content_type, data from survey_logos where survey_id = %s", (survey_id,)
    ).fetchone()


def delete_logo(conn: psycopg.Connection, survey_id: UUID) -> bool:
    """Remove the logo. False if there is no such survey (no logo is fine)."""
    found = conn.execute(
        "update surveys set logo_updated_at = null, updated_at = now() where id = %s",
        (survey_id,),
    ).rowcount
    conn.execute("delete from survey_logos where survey_id = %s", (survey_id,))
    return found == 1
