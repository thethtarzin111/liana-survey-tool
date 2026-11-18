from typing import Annotated

from fastapi import APIRouter, Depends, Query

from liana_survey_shared.web.db import TenantDB, tenant_db

from . import domain, repo
from .schemas import PerformanceRow

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
