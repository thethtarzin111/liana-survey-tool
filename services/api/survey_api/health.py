from fastapi import APIRouter, Response, status

from liana_survey_shared.db import ping

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up. Does not touch the database."""
    return {"status": "ok"}


@router.get("/health/ready")
def ready(response: Response) -> dict[str, str]:
    """Readiness: the database answers."""
    if ping():
        return {"status": "ready", "database": "ok"}
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "not ready", "database": "unreachable"}
