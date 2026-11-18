from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from data_analyzer import repo
from data_analyzer.main import app
from liana_survey_shared.web.db import tenant_db


class Connection:
    found = True

    def execute(self, *args):
        return self

    def fetchone(self):
        return {"id": "survey"} if self.found else None


@pytest.fixture
def client():
    connection = Connection()

    @contextmanager
    def connect():
        yield connection

    app.dependency_overrides[tenant_db] = lambda: connect
    yield TestClient(app), connection
    app.dependency_overrides.clear()


def test_comments_pass_segment_to_repository(client, monkeypatch):
    http, _ = client
    calls = []
    monkeypatch.setattr(repo, "comments", lambda conn, survey, segment: calls.append(segment) or [])
    response = http.get(f"/api/v1/results/{uuid4()}/comments?segment=members")
    assert response.status_code == 200
    assert response.json() == []
    assert calls == ["members"]


def test_reasons_are_ranked_and_filtered(client, monkeypatch):
    http, _ = client
    calls = []

    def charts(conn, survey, segment):
        calls.append(segment)
        return [
            {
                "kind": "reasons",
                "options": [{"label": "Price", "count": 1}, {"label": "Quality", "count": 3}],
            },
            {"kind": "rating", "options": []},
        ]

    monkeypatch.setattr(repo, "question_charts", charts)
    response = http.get(f"/api/v1/results/{uuid4()}/reasons?segment=partners")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["options"][0]["label"] == "Quality"
    assert calls == ["partners"]


@pytest.mark.parametrize("tab", ["reasons", "comments"])
def test_missing_survey_and_invalid_segment(client, tab):
    http, connection = client
    connection.found = False
    url = f"/api/v1/results/{uuid4()}/{tab}"
    assert http.get(url).status_code == 404
    assert http.get(url + "?segment=invalid%20segment").status_code == 422
