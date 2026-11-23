"""Survey Manager service (report Figure 1): surveys, questions, templates,
publishing and links, and the follow-up of contact requests. Requirements R02,
R06, R07.

Reached through the API gateway at /api/v1/surveys, /api/v1/templates and
/api/v1/contact-requests.
"""

from fastapi import FastAPI

from liana_survey_shared.web.health import health_router

from .contact_requests.routes import router as contact_requests_router
from .questions.routes import router as questions_router
from .surveys.routes import router as surveys_router
from .templates.routes import router as templates_router

app = FastAPI(title="LianaSurvey Survey Manager", version="0.1.0")

app.include_router(health_router())
app.include_router(surveys_router)
app.include_router(questions_router)
app.include_router(templates_router)
app.include_router(contact_requests_router)
