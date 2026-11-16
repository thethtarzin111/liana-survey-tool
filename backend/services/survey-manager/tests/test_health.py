from fastapi.testclient import TestClient

from survey_manager.main import app

client = TestClient(app)


def test_health_is_ok_without_database():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
