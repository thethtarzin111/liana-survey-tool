from liana_survey_shared.config import Settings

from .adapters.lianaautomation.adapter import LianaAutomationContactEvents
from .adapters.mock.adapter import MockContactEvents
from .ports.contact_events import ContactEvents


def build_contact_events(settings: Settings) -> ContactEvents:
    """Pick the adapter from LIANA_ADAPTER."""
    if settings.liana_adapter == "mock":
        return MockContactEvents()
    if settings.liana_adapter == "lianaautomation":
        return LianaAutomationContactEvents(
            settings.lianaautomation_base_url,
            settings.lianaautomation_client_id,
            settings.lianaautomation_client_secret,
        )
    raise ValueError(f"Unknown LIANA_ADAPTER: {settings.liana_adapter}")
