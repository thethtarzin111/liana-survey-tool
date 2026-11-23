"""Stores whether a contact request, and later its "You said, we did" reply,
reached LianaAutomation, for the Contact requests page and the Close the loop
tab. The connector writes only these columns of contact_requests."""

from liana_survey_shared.db import tenant_connection
from liana_survey_shared.messages import ContactResolved

from .handlers import DeliveryStatus, TrackedEvent


def record_contact_request_status(
    event: TrackedEvent, status: DeliveryStatus, attempts: int
) -> None:
    if isinstance(event, ContactResolved):
        sql = """update contact_requests set reply_status = %s, reply_attempts = %s
                 where id = %s"""
    else:
        sql = """update contact_requests
                 set liana_status = %s, liana_attempts = %s, liana_updated_at = now()
                 where id = %s"""
    with tenant_connection(event.tenant_id) as conn:
        conn.execute(sql, (status, attempts, event.contact_request_id))
