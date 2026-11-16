from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from liana_survey_shared.config import get_settings
from liana_survey_shared.web.auth import CurrentUser, current_user
from liana_survey_shared.web.health import health_router

app = FastAPI()
app.include_router(health_router(needs_database=False))


@app.get("/who")
def who(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    return user


client = TestClient(app)


def test_user_comes_from_gateway_headers():
    tenant, user = uuid4(), uuid4()
    r = client.get(
        "/who",
        headers={
            "X-Tenant-Id": str(tenant),
            "X-User-Id": str(user),
            "X-Tenant-Name": "Other Org",
            "X-User-Name": "Ola",
            "X-User-Email": "ola@example.org",
        },
    )
    assert r.status_code == 200
    assert r.json()["tenant_id"] == str(tenant)
    assert r.json()["name"] == "Ola"


def test_without_headers_dev_mode_is_the_demo_user():
    r = client.get("/who")
    assert r.status_code == 200
    assert r.json()["name"] == "Anna Virtanen"
    assert r.json()["tenant_name"] == "Example Members Association"


def test_without_headers_outside_dev_mode_is_401(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "liana")
    get_settings.cache_clear()
    try:
        assert client.get("/who").status_code == 401
    finally:
        monkeypatch.delenv("AUTH_MODE")
        get_settings.cache_clear()


def test_bad_tenant_header_is_rejected():
    r = client.get("/who", headers={"X-Tenant-Id": "nope", "X-User-Id": str(uuid4())})
    assert r.status_code == 422


@pytest.mark.parametrize("path", ["/health", "/health/ready"])
def test_health_without_database(path):
    assert client.get(path).status_code == 200
