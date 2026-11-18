from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from data_analyzer import repo
from data_analyzer.main import app
from liana_survey_shared.web.db import tenant_db


@pytest.fixture
def client():
    @contextmanager
    def connect():
        yield object()

    app.dependency_overrides[tenant_db] = lambda: connect
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_filters_and_pagination_reach_repository(client, monkeypatch):
    calls = []
    monkeypatch.setattr(repo, "response_feed", lambda *args: calls.append(args[1:]) or [])
    survey = uuid4()
    response = client.get(
        f"/api/v1/results/responses?survey_id={survey}&segment=members&limit=20&offset=40"
    )
    assert response.status_code == 200
    assert response.json() == []
    assert calls == [(survey, "members", 20, 40)]


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=501", "offset=-1", "survey_id=nope", "segment=a%20b"]
)
def test_invalid_filters_are_rejected(client, query):
    assert client.get("/api/v1/results/responses?" + query).status_code == 422
