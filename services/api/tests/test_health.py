from fastapi.testclient import TestClient

from survey_api.main import app

client = TestClient(app)


def test_health_is_ok_without_database():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_me_returns_demo_user_in_dev_mode():
    r = client.get("/api/v1/me")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Anna Virtanen"
    assert body["tenant_name"] == "Example Members Association"
