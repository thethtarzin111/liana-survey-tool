"""Respondent Survey Service (report Figure 1): the public answer path.
Requirements R01, R05, R07, R08.

Stateless and light, so it can scale on its own during newsletter bursts:
it verifies the signed link token, puts the answer on the survey.answers
queue and returns a server-rendered thank-you page. The Background Worker
saves answers at its own pace. No login: the gateway routes /r/ here
without a user.

Endpoints come with backlog card #42 (answer endpoint and thank-you page).
"""

from fastapi import FastAPI

from liana_survey_shared.web.health import health_router

app = FastAPI(title="LianaSurvey Respondent Service", version="0.1.0")

# Answers go to the queue; the worker writes the database.
app.include_router(health_router(needs_database=False))
