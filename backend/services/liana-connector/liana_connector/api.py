"""The connector's HTTP API at /api/v1/integrations (the Integrations page).

The connector is the only part that talks to Liana products, so testing a
connection, listing channels and sending test events live here, next to the
queue consumer in main.py. Run with: uvicorn liana_connector.api:app
"""

from fastapi import FastAPI

from liana_survey_shared.web.health import health_router

from .automation.routes import router

app = FastAPI(title="LianaSurvey Liana Connector", version="0.1.0")

app.include_router(health_router(needs_database=True))
app.include_router(router)
