"""Plain survey rules, no SQL or HTTP. Keeping them here keeps a later PHP port simple."""

from .schemas import TITLE_MAX, SurveyStatus, Title

# Which statuses each list action may start from, and where it leads.
CLOSE_FROM = frozenset({SurveyStatus.live})
UNPUBLISH_FROM = frozenset({SurveyStatus.live, SurveyStatus.scheduled})

COPY_SUFFIX = " (copy)"


class StatusChangeNotAllowed(Exception):
    """The survey's current status does not allow this action."""

    def __init__(self, action: str, current: SurveyStatus):
        super().__init__(f"A {current.value} survey cannot be {action}.")


def closed_status(current: SurveyStatus) -> SurveyStatus:
    """Closing stops a live survey from taking answers."""
    if current not in CLOSE_FROM:
        raise StatusChangeNotAllowed("closed", current)
    return SurveyStatus.closed


def unpublished_status(current: SurveyStatus) -> SurveyStatus:
    """Unpublishing turns a live or scheduled survey back into a draft."""
    if current not in UNPUBLISH_FROM:
        raise StatusChangeNotAllowed("unpublished", current)
    return SurveyStatus.draft


def copy_title(title: Title) -> str:
    """Title of a duplicated survey, kept within the title limit."""
    return title[: TITLE_MAX - len(COPY_SUFFIX)].rstrip() + COPY_SUFFIX
