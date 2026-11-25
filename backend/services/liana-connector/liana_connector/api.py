"""The connector's HTTP API at /api/v1/integrations (the Integrations page).

The connector is the only part that talks to Liana products, so testing a
connection, listing channels and sending test events live here, next to the
queue consumer in main.py. Run with: uvicorn liana_connector.api:app
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from liana_survey_shared.config import get_settings
from liana_survey_shared.web.health import health_router

from .automation import secrets
from .automation.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Refuse to start with the public default key outside local development.
    settings = get_settings()
    secrets.check_key(settings.integration_secret_key, settings.auth_mode)
    yield


app = FastAPI(title="LianaSurvey Liana Connector", version="0.1.0", lifespan=lifespan)

app.include_router(health_router(needs_database=True))
app.include_router(router)
