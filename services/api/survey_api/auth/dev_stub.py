"""Dev-auth stub.

There is no login screen in this project. Every request is treated as the
demo user from .env. Liana's real login plugs in here later: replace
current_user() with one that reads Liana's session or token, and keep the
CurrentUser shape so the rest of the code does not change.
"""

from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel

from liana_survey_shared.config import get_settings


class CurrentUser(BaseModel):
    user_id: UUID
    tenant_id: UUID
    tenant_name: str
    name: str
    email: str


def current_user() -> CurrentUser:
    s = get_settings()
    if s.auth_mode != "dev":
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Only AUTH_MODE=dev is available")
    return CurrentUser(
        user_id=s.dev_user_id,
        tenant_id=s.dev_tenant_id,
        tenant_name=s.dev_tenant_name,
        name=s.dev_user_name,
        email=s.dev_user_email,
    )
