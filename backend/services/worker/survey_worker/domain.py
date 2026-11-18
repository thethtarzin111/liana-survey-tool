"""Plain rules for the "new responses" emails to a survey's owner.

The first new response is emailed right away. Responses that arrive within the
interval after an email are held, then sent together as one digest once the
interval has passed. No new responses, no email.
"""

from datetime import datetime, timedelta
from uuid import UUID

from liana_survey_shared.messages import NewResponsesDigest


def new_responses_due(
    *,
    total: int,
    notified_count: int,
    last_sent_at: datetime | None,
    now: datetime,
    interval: timedelta,
) -> int:
    """How many new responses to email about now. 0 means send nothing yet.

    `notified_count` is the response total the last email covered, and
    `last_sent_at` is when it went out (None before the first email)."""
    new = total - notified_count
    if new <= 0:
        return 0
    if last_sent_at is not None and now - last_sent_at < interval:
        return 0
    return new


def results_url(app_base_url: str, survey_id: UUID) -> str:
    return f"{app_base_url.rstrip('/')}/results?survey={survey_id}"


def digest(
    *,
    tenant_id: UUID,
    survey_id: UUID,
    survey_title: str,
    new_responses: int,
    total_responses: int,
    app_base_url: str,
    recipient_email: str,
    recipient_name: str,
) -> NewResponsesDigest:
    """The message for the connector: counts and a link, never answers."""
    return NewResponsesDigest(
        tenant_id=tenant_id,
        survey_id=survey_id,
        survey_title=survey_title,
        new_responses=new_responses,
        total_responses=total_responses,
        results_url=results_url(app_base_url, survey_id),
        recipient_email=recipient_email,
        recipient_name=recipient_name,
    )
