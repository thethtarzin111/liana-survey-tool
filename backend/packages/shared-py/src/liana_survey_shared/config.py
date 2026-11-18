"""Settings read from environment variables (see .env.example)."""

from functools import lru_cache
from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Services connect as the app user, so row-level security applies.
    database_url: str = "postgresql://survey_app:change-me-app@localhost:5432/survey"
    rabbitmq_url: str = "amqp://survey:change-me-rabbit@localhost:5672/"

    # Answer links (#5, #42): where readers open them, and the key that signs them.
    # Set LINK_SIGNING_SECRET to a long random value outside local development.
    public_base_url: str = "http://localhost:8000"
    link_signing_secret: str = "change-me-link-secret"
    # LianaMailer's placeholder for the contact id in newsletter snippet links (#40).
    mailer_reader_tag: str = "$id$"

    # Where the admin app runs; "new responses" emails link to its results page.
    app_base_url: str = "http://localhost:4200"
    # "New responses" emails: at most one per survey per interval. The worker
    # checks for due emails every sweep.
    response_digest_interval_seconds: int = Field(default=3600, gt=0)
    response_digest_sweep_seconds: int = Field(default=60, gt=0)

    auth_mode: str = "dev"
    dev_tenant_id: UUID = UUID("00000000-0000-4000-8000-000000000001")
    dev_tenant_name: str = "Example Members Association"
    dev_user_id: UUID = UUID("00000000-0000-4000-8000-000000000101")
    dev_user_name: str = "Anna Virtanen"
    dev_user_email: str = "anna.virtanen@example.org"

    liana_adapter: str = "mock"
    lianaautomation_base_url: str = "https://rest.automation.lianacloud.com/api/v1"
    lianaautomation_client_id: str = ""
    lianaautomation_client_secret: str = ""
    # mock = log the email only. No real mail adapter yet.
    notification_mail_adapter: str = "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
