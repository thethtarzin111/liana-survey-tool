from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from liana_survey_shared.web.db import TenantDB, tenant_db

from . import domain, repo
from .schemas import PerformanceRow, SurveyOverview

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


@router.get("/{survey_id}/overview", response_model=SurveyOverview)
def survey_overview(
    survey_id: UUID,
    segment: Annotated[
        str, Query(description="`all` for no filter, or a value from `segments`")
    ] = "all",
    db: TenantDB = Depends(tenant_db),
) -> dict:
    """KPIs, a summary per question, reasons, trend and per-segment scores for one survey."""
    with db() as conn:
        counts = repo.segment_counts(conn, survey_id)
        if counts is None:
            raise HTTPException(404, "Survey not found")
        stored = None
        if segment != "all":
            stored = domain.stored_segments(domain.available_groups(counts), segment)
            if stored is None:
                raise HTTPException(400, "Segment not available")
        rows = repo.overview_rows(conn, survey_id, stored, domain.TIME_ZONE.key)
    if rows is None:
        raise HTTPException(404, "Survey not found")
    return domain.overview(rows, segment)
