"""The text of the emails sent through the notification mail port."""

from liana_survey_shared.messages import NewResponsesDigest

from .ports.notification_mail import Email


def _count(count: int, what: str) -> str:
    return f"{count} {what}" if count == 1 else f"{count} {what}s"


def new_responses_email(digest: NewResponsesDigest) -> Email:
    """Counts and a link to the results. The message holds no answers, so the
    email cannot show any."""
    new = _count(digest.new_responses, "new response")
    return Email(
        to_address=digest.recipient_email,
        to_name=digest.recipient_name,
        subject=f"{digest.survey_title}: {new}",
        text=(
            f"Hello {digest.recipient_name},\n\n"
            f'Your survey "{digest.survey_title}" has {new}'
            f" ({_count(digest.total_responses, 'response')} in total).\n\n"
            f"See the results: {digest.results_url}\n"
        ),
    )
