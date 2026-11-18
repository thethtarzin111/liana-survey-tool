import csv
import io
from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from liana_survey_shared.web.db import TenantDB, tenant_db

from . import domain, repo
from .schemas import PerformanceRow, ResponseDetail, ResponsesPage, SurveyOverview

router = APIRouter(prefix="/api/v1/results", tags=["results"])


@router.get("/performance", response_model=list[PerformanceRow])
def survey_performance(
    limit: Annotated[
        int | None, Query(ge=1, le=100, description="Surveys to include; all when left out")
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Surveys to skip")] = 0,
    db: TenantDB = Depends(tenant_db),
) -> list[dict]:
    """Views, responses and response rate for every used survey channel. Surveys with
    the latest views or answers come first; `limit` counts surveys, not rows."""
    with db() as conn:
        rows = repo.performance_rows(conn, limit=limit, offset=offset)
    return [domain.performance_row(row) for row in rows]


SegmentQuery = Annotated[
    str, Query(description="`all` for no filter, or a `value` from the overview's `segments`")
]


def resolve_scope(
    conn: psycopg.Connection, survey_id: UUID, value: str
) -> tuple[tuple[str, ...] | None, dict[str, str]]:
    """The stored segments a filter value stands for (None for `all`) and the label of
    every stored segment (empty when segments are off). Raises 404 or 400."""
    counts = repo.segment_counts(conn, survey_id)
    if counts is None:
        raise HTTPException(404, "Survey not found")
    groups = domain.available_groups(counts)
    stored = None
    if value != "all":
        stored = domain.stored_segments(groups, value)
        if stored is None:
            raise HTTPException(400, "Segment not available")
    return stored, domain.segment_labels(groups)


def resolve_segment(
    conn: psycopg.Connection, survey_id: UUID, value: str
) -> tuple[str, ...] | None:
    """The stored segments a filter value stands for, None for `all`. Raises 404 or 400."""
    return resolve_scope(conn, survey_id, value)[0]


def resolve_group(
    conn: psycopg.Connection, survey_id: UUID, group: str | None
) -> tuple[int, ...] | None:
    """The answers of an answer group of the survey's main question. Raises 422."""
    if not group:
        return None
    values = domain.group_values(repo.scale_kind(conn, survey_id), group)
    if values is None:
        raise HTTPException(422, "Unknown answer group")
    return values


Search = Annotated[str | None, Query(description="Text to find in the masked comments")]
Group = Annotated[
    str | None,
    Query(
        description="Answer group: thumbs not-for-me, good, loved-it; nps detractors, "
        "passives, promoters; rating low, neutral, high"
    ),
]


@router.get("/{survey_id}/overview", response_model=SurveyOverview)
def survey_overview(
    survey_id: UUID,
    segment: SegmentQuery = "all",
    db: TenantDB = Depends(tenant_db),
) -> dict:
    """KPIs, a summary per question, reasons, trend and per-segment scores for one survey."""
    with db() as conn:
        stored = resolve_segment(conn, survey_id, segment)
        rows = repo.overview_rows(conn, survey_id, stored, domain.TIME_ZONE.key)
    if rows is None:
        raise HTTPException(404, "Survey not found")
    return domain.overview(rows, segment)


@router.get("/{survey_id}/responses", response_model=ResponsesPage)
def survey_responses(
    survey_id: UUID,
    segment: SegmentQuery = "all",
    q: Search = None,
    group: Group = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: TenantDB = Depends(tenant_db),
) -> dict:
    """Responses of one survey, newest first. Emails and phone numbers in comments are
    hidden, and the search, the count and the paging use the hidden text."""
    with db() as conn:
        stored, labels = resolve_scope(conn, survey_id, segment)
        values = resolve_group(conn, survey_id, group)
        total, rows = repo.responses(conn, survey_id, stored, q, values, limit, offset)
    return {"total": total, "rows": [domain.response_row(row, labels) for row in rows]}


@router.get("/{survey_id}/responses.csv")
def survey_responses_csv(
    survey_id: UUID,
    segment: SegmentQuery = "all",
    q: Search = None,
    group: Group = None,
    db: TenantDB = Depends(tenant_db),
) -> StreamingResponse:
    """Every matching response as CSV: ID, Received, Segment and one column per question."""
    with db() as conn:
        stored, labels = resolve_scope(conn, survey_id, segment)
        values = resolve_group(conn, survey_id, group)
        questions, rows = repo.responses_export(conn, survey_id, stored, q, values)
    lines = domain.csv_rows(questions, rows, labels)

    def stream() -> Iterator[str]:
        for line in lines:
            buffer = io.StringIO()
            csv.writer(buffer).writerow(line)
            yield buffer.getvalue()

    return StreamingResponse(
        stream(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="responses.csv"'},
    )


@router.get("/{survey_id}/responses/{response_id}", response_model=ResponseDetail)
def survey_response(survey_id: UUID, response_id: UUID, db: TenantDB = Depends(tenant_db)) -> dict:
    """Every answer of one response, masked like the list."""
    with db() as conn:
        _, labels = resolve_scope(conn, survey_id, "all")
        detail = repo.response_detail(conn, survey_id, response_id)
    if detail is None:
        raise HTTPException(404, "Response not found")
    return domain.response_detail(detail, labels)
