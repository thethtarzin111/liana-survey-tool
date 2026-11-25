from liana_survey_shared.config import Settings

from .adapters.lianaautomation.adapter import LianaAutomationContactEvents
from .adapters.lianamailer.directory import DEMO_HOST, DemoDirectory, LianaMailerDirectory, NotSetUp
from .adapters.mock.adapter import MockContactEvents
from .adapters.mock.mail import MockNotificationMail
from .automation import secrets
from .ports.contact_directory import ContactDirectory
from .ports.contact_events import ContactEvents
from .ports.notification_mail import NotificationMail


def build_contact_directory(settings: Settings) -> ContactDirectory:
    """LianaMailer from LIANAMAILER_API_*: the real API, the demo fake (dev mode
    only), or "not set up" when the settings are missing."""
    host = settings.lianamailer_api_host.strip()
    if host == DEMO_HOST:
        if settings.auth_mode != "dev":
            return NotSetUp("LIANAMAILER_API_HOST=demo only works in local development.")
        return DemoDirectory()
    if not (host and settings.lianamailer_api_user and settings.lianamailer_api_secret):
        return NotSetUp()
    return LianaMailerDirectory(
        host,
        settings.lianamailer_api_user,
        settings.lianamailer_api_secret,
        settings.lianamailer_api_realm,
    )


def build_contact_events(settings: Settings) -> ContactEvents:
    """Pick the adapter from LIANA_ADAPTER."""
    if settings.liana_adapter == "mock":
        return MockContactEvents()
    if settings.liana_adapter == "lianaautomation":
        # Each organisation's own connection, saved on the Integrations page. Refuses
        # to start with the repo's default key outside dev mode (secrets.check_key).
        return LianaAutomationContactEvents(
            secrets.check_key(settings.integration_secret_key, settings.auth_mode),
            allow_demo=settings.auth_mode == "dev",
            directory=build_contact_directory(settings),
        )
    raise ValueError(f"Unknown LIANA_ADAPTER: {settings.liana_adapter}")


def build_notification_mail(settings: Settings) -> NotificationMail:
    """Pick the adapter from NOTIFICATION_MAIL_ADAPTER. Only the mock exists yet."""
    if settings.notification_mail_adapter == "mock":
        return MockNotificationMail()
    raise ValueError(f"Unknown NOTIFICATION_MAIL_ADAPTER: {settings.notification_mail_adapter}")
