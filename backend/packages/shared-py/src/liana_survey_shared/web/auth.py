"""Who is calling: the user the API gateway signed in.

The gateway (backend/services/gateway) is the only way in from outside. It
authenticates the request and forwards the user as headers. It always
overwrites these headers, so a client cannot set them itself. The services
are not reachable from outside, so they trust the headers.

Dev mode (AUTH_MODE=dev): the gateway sends the demo user from .env. A request
that reaches a service directly without the headers (unit tests, Swagger on a
service's own port) is also treated as the demo user. In any other mode a
missing user is 401.
"""

from uuid import UUID

from fastapi import Header, HTTPException, status
from pydantic import BaseModel

from ..config import get_settings

TENANT_HEADER = "X-Tenant-Id"
USER_HEADER = "X-User-Id"


class CurrentUser(BaseModel):
    user_id: UUID
    tenant_id: UUID
    tenant_name: str
    name: str
    email: str


def demo_user() -> CurrentUser:
    s = get_settings()
    return CurrentUser(
        user_id=s.dev_user_id,
        tenant_id=s.dev_tenant_id,
        tenant_name=s.dev_tenant_name,
        name=s.dev_user_name,
        email=s.dev_user_email,
    )


def current_user(
    x_tenant_id: UUID | None = Header(default=None, include_in_schema=False),
    x_user_id: UUID | None = Header(default=None, include_in_schema=False),
    x_tenant_name: str = Header(default="", include_in_schema=False),
    x_user_name: str = Header(default="", include_in_schema=False),
    x_user_email: str = Header(default="", include_in_schema=False),
) -> CurrentUser:
    """FastAPI dependency: the signed-in user, from the gateway's headers."""
    if x_tenant_id and x_user_id:
        return CurrentUser(
            user_id=x_user_id,
            tenant_id=x_tenant_id,
            tenant_name=x_tenant_name,
            name=x_user_name,
            email=x_user_email,
        )
    if get_settings().auth_mode == "dev":
        return demo_user()
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
