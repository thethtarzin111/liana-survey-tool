"""The contact rules (#44), shared by the respondent service and the worker.

Answers are anonymous by default. An answer is linked to a contact only

- when the survey offers the "Contact me about this by email" opt-in and the
  reader ticks it (the worker turns it into a contact request), or
- when the survey's owner set it to identified answers (surveys.anonymous off);
  the answer pages then tell the reader so,

and then only by the LianaMailer contact reference from the link, never by an
e-mail address (CLAUDE.md, privacy).
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


def answer_contact_ref(
    *,
    identified_survey: bool,
    survey_offers_opt_in: bool,
    reader_opted_in: bool,
    contact_ref: str | None,
) -> str | None:
    """The contact reference to keep with an answer from a link, or None.

    Unlike contact_ref_to_store() this never raises: without a usable reference
    the answer stays anonymous (and no contact request is made)."""
    if not (identified_survey or (survey_offers_opt_in and reader_opted_in)):
        return None
    ref = (contact_ref or "").strip()
    if not ref or _EMAIL.search(ref):
        return None
    return ref
