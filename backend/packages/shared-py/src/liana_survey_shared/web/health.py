"""Health endpoints, the same in every HTTP service."""

from fastapi import APIRouter, Response, status

from ..db import ping


def health_router(needs_database: bool = True) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    def health() -> dict[str, str]:
        """Liveness: the process is up. Does not touch the database."""
        return {"status": "ok"}

    @router.get("/health/ready")
    def ready(response: Response) -> dict[str, str]:
        """Readiness: the service can do its work (database reachable if it needs one)."""
        if not needs_database:
            return {"status": "ready"}
        if ping():
            return {"status": "ready", "database": "ok"}
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not ready", "database": "unreachable"}

    return router
