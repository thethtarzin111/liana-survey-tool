"""Survey Manager service (report Figure 1): surveys, questions, templates,
publishing and links. Requirements R02, R06, R07.

Reached through the API gateway at /api/v1/surveys and /api/v1/templates.
"""

from fastapi import FastAPI

from liana_survey_shared.web.health import health_router

from .surveys.routes import router as surveys_router

app = FastAPI(title="LianaSurvey Survey Manager", version="0.1.0")

app.include_router(health_router())
app.include_router(surveys_router)
