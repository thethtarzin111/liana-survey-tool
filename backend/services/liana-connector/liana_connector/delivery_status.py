"""Stores whether a contact request reached LianaAutomation, for the Contact
requests page. The connector writes only these three columns."""

from liana_survey_shared.db import tenant_connection
from liana_survey_shared.messages import ContactRequested

from .handlers import DeliveryStatus


def record_contact_request_status(
    event: ContactRequested, status: DeliveryStatus, attempts: int
) -> None:
    with tenant_connection(event.tenant_id) as conn:
        conn.execute(
            """update contact_requests
               set liana_status = %s, liana_attempts = %s, liana_updated_at = now()
               where id = %s""",
            (status, attempts, event.contact_request_id),
        )
