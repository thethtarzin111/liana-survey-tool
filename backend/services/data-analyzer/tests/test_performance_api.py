"""GET /api/v1/results/performance (#12). Needs a migrated Postgres reached as the
app role; the test deletes the survey it creates."""

import os
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from data_analyzer.main import app
from liana_survey_shared.db import ping, tenant_connection
from liana_survey_shared.scoring import headline

DEMO_TENANT = UUID("00000000-0000-4000-8000-000000000001")
DEMO_USER = UUID("00000000-0000-4000-8000-000000000101")
HEADERS = {"X-Tenant-Id": str(DEMO_TENANT), "X-User-Id": str(DEMO_USER)}
needs_db = pytest.mark.skipif(
    not os.environ.get("REQUIRE_DB") and not ping(), reason="no database (set DATABASE_URL)"
)


@pytest.fixture
def survey():
    """An NPS survey answered 10 and 9 by email and 0 by QR code, viewed 4 and 2 times."""
    with tenant_connection(DEMO_TENANT) as conn:
        survey_id = conn.execute(
            """insert into surveys (tenant_id, title, type, status)
               values (%s, 'Performance test', 'nps', 'live') returning id""",
            (DEMO_TENANT,),
        ).fetchone()[0]
        main_id = conn.execute(
            """insert into questions (tenant_id, survey_id, position, kind, prompt)
               values (%s, %s, 1, 'nps', 'Recommend us?') returning id""",
            (DEMO_TENANT, survey_id),
        ).fetchone()[0]
        for key, channel, value in (("a", "email", 10), ("b", "email", 9), ("c", "qr", 0)):
            response_id = conn.execute(
                """insert into responses (tenant_id, survey_id, link_token_hash, channel)
                   values (%s, %s, %s, %s) returning id""",
                (DEMO_TENANT, survey_id, key, channel),
            ).fetchone()[0]
            conn.execute(
                """insert into answers (tenant_id, response_id, question_id, value_number)
                   values (%s, %s, %s, %s)""",
                (DEMO_TENANT, response_id, main_id, value),
            )
        conn.execute(
            """insert into survey_channel_views (survey_id, tenant_id, channel, view_count)
               values (%s, %s, 'email', 4), (%s, %s, 'qr', 2)""",
            (survey_id, DEMO_TENANT, survey_id, DEMO_TENANT),
        )
    yield survey_id
    with tenant_connection(DEMO_TENANT) as conn:
        conn.execute("delete from surveys where id = %s", (survey_id,))


@pytest.mark.db
@needs_db
def test_each_channel_row_has_its_own_rate_and_main_result(survey):
    r = TestClient(app).get("/api/v1/results/performance", headers=HEADERS)
    assert r.status_code == 200
    rows = {row["channel"]: row for row in r.json() if row["survey_id"] == str(survey)}

    assert set(rows) == {"email", "qr"}  # no row for a channel nobody used
    assert (rows["email"]["views"], rows["email"]["responses"]) == (4, 2)
    assert rows["email"]["response_rate"] == 50
    assert rows["email"]["main_result"] == headline("nps", {"10": 1, "9": 1}).score
    assert (rows["qr"]["views"], rows["qr"]["responses"]) == (2, 1)
    assert rows["qr"]["main_result"] == headline("nps", {"0": 1}).score
    assert rows["email"]["main_result"] != rows["qr"]["main_result"]
