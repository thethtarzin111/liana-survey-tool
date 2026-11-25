"""The contact rules, shared by the respondent service and the worker.

- An answer from a newsletter link (r=, the reader's LianaMailer contact id) is
  identified: the contact id is stored with it and the answer is sent to
  LianaAutomation. The answer page tells the reader so.
- An answer from the public link or the QR code has no contact id and stays
  anonymous. Its reader can tick "Contact me" and give an email address.
- An email address is kept only for a reader who asked to be contacted
  (responses.contact_email), so the survey's owner can reply.

The connector turns a contact id into an email address through the LianaMailer
API, because LianaAutomation matches contacts by email.
"""

import re

_EMAIL_LIKE = re.compile(r"[^@\s]+@[^@\s]+")
#: An address someone can be reached at: one @, a dot in the domain, no spaces.
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s.]+")
#: The longest address SMTP allows.
EMAIL_MAX_LENGTH = 254


class InvalidEmail(ValueError):
    """The typed email address can't be used to reach the reader."""


def answer_contact_ref(contact_ref: str | None) -> str | None:
    """The contact id to keep with an answer from a link, or None (anonymous).

    Never an email address: a reference that looks like one is dropped."""
    ref = (contact_ref or "").strip()
    if not ref or _EMAIL_LIKE.search(ref):
        return None
    return ref


def clean_email(value: str | None) -> str:
    """The typed address, trimmed and lower-cased. Raises InvalidEmail."""
    email = (value or "").strip().lower()
    if len(email) > EMAIL_MAX_LENGTH or not _EMAIL.fullmatch(email):
        raise InvalidEmail("not an email address")
    return email
