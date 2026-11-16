"""The contact opt-in rule (#44), shared by the respondent service and the worker.

Answers are anonymous by default. Only when the survey offers the "Contact me about
this by email" opt-in and the reader ticks it is the answer linked to a contact,
and then only by a LianaMailer contact reference, never by an e-mail address
(CLAUDE.md, privacy). The worker turns that reference into a contact request.
"""

import re

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+")


class ContactRefError(ValueError):
    """The contact reference is missing or is not allowed to be stored."""


def contact_ref_to_store(
    survey_offers_opt_in: bool, reader_opted_in: bool, contact_ref: str | None
) -> str | None:
    """The contact reference to keep with an answer, or None to keep it anonymous.

    Raises ContactRefError when the reader opted in but there is no usable
    reference, or when the value looks like an e-mail address."""
    if not (survey_offers_opt_in and reader_opted_in):
        return None
    ref = (contact_ref or "").strip()
    if not ref:
        raise ContactRefError("a contact reference is needed when the reader opts in")
    if _EMAIL.search(ref):
        raise ContactRefError("store a contact reference, never an e-mail address")
    return ref
