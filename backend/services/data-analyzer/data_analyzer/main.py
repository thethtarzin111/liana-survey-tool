"""Data Analyzer service (report Figure 1): results. Requirements R03, R04, R08.

Reads results from the Survey DB (aggregates kept by the worker), computes
NPS and CSAT with the standard formulas, and serves them to the admin app at
/api/v1/results through the gateway. It also sends identified answers and
"Contact me" requests to the integration queue (survey.liana-events), which
the Liana connector forwards to LianaAutomation.

Endpoints come with backlog cards #22, #15 and #50.
"""

from fastapi import FastAPI

from liana_survey_shared.web.health import health_router

from .routes import router

app = FastAPI(title="LianaSurvey Data Analyzer", version="0.1.0")

app.include_router(health_router(needs_database=True))
app.include_router(router)
