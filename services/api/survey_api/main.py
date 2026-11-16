"""LianaSurvey API.

Modules (each can become its own service later, see docs/decisions/0002):
- modules/surveys     survey manager: surveys, questions, templates, publishing
- modules/analytics   NPS / CSAT and other results
- modules/respondent  public answer endpoint: queues answers, returns a thank-you page
"""

from fastapi import Depends, FastAPI

from . import health
from .auth.dev_stub import CurrentUser, current_user
from .modules.surveys.router import router as surveys_router

app = FastAPI(title="LianaSurvey API", version="0.1.0")

app.include_router(health.router)
app.include_router(surveys_router)


@app.get("/api/v1/me", response_model=CurrentUser, tags=["auth"])
def me(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    """The signed-in user. In dev mode this is always the demo user."""
    return user
