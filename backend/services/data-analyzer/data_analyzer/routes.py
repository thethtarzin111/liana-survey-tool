from fastapi import APIRouter, Depends

from liana_survey_shared.scoring import headline
from liana_survey_shared.web.db import TenantDB, tenant_db

from . import repo
from .performance import response_rate
from .schemas import PerformanceRow

router = APIRouter(prefix="/api/v1/results", tags=["results"])


@router.get("/performance", response_model=list[PerformanceRow])
def survey_performance(db: TenantDB = Depends(tenant_db)) -> list[dict]:
    """Views, responses and response rate for every used survey channel."""
    with db() as conn:
        rows = repo.performance_rows(conn)
    result = []
    for row in rows:
        score = headline(row["type"], row["distribution"])
        result.append(
            {
                **row,
                "response_rate": response_rate(row["responses"], row["views"]),
                "main_result": score.score if score else None,
            }
        )
    return result
