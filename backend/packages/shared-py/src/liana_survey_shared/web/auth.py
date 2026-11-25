"""Who is calling: the user the API gateway signed in.

The local gateway (backend/scripts/local_gateway.py) overwrites admin identity
headers with the configured demo user. Production ingress must authenticate
requests, overwrite identity headers, and keep the services private, since
they trust the forwarded identity.

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


# A second demo organisation (backend/db/seed/seed.sql). The dev-auth gateway can
# switch to it, to show that organisations never see each other's data.
SECOND_DEMO_USER = CurrentUser(
    user_id=UUID("00000000-0000-4000-8000-000000000102"),
    tenant_id=UUID("00000000-0000-4000-8000-000000000002"),
    tenant_name="LUT Students",
    name="Mikko Korhonen",
    email="mikko.korhonen@example.org",
)


def demo_users() -> list[CurrentUser]:
    """The demo users the dev-auth gateway can sign in as, one per organisation.
    The configured demo user comes first and is the default."""
    first = demo_user()
    if SECOND_DEMO_USER.tenant_id == first.tenant_id:
        return [first]
    return [first, SECOND_DEMO_USER]


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
