"""Respondent Survey Service (report Figure 1): the public answer path.
Requirements R01, R05, R07, R08.

Light, so it can scale on its own during newsletter bursts: it checks the
signed answer link, puts the answer on the survey.answers queue and returns a
server-rendered thank-you page. The Background Worker saves answers at its own
pace. No login: the gateway routes /r/ here without a user.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from liana_survey_shared.web.health import health_router

from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # The queue publisher is made on the first answer (routes.get_answer_queue).
    queue = getattr(app.state, "answer_queue", None)
    if queue is not None:
        await queue.close()


app = FastAPI(title="LianaSurvey Respondent Service", version="0.1.0", lifespan=lifespan)

# It reads the survey (status, main question, thank-you message) to check answers.
app.include_router(health_router(needs_database=True))
app.include_router(router)
