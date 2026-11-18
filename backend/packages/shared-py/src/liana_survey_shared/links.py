"""Answer links (#5, #42): signed, per reader, so a reader's second tap counts once.

    {public_base_url}/r/{survey_token}?r={reader_ref}&s={signature}&a={answer}

- survey_token: the survey's random public token (set when it is first published).
- reader_ref: who the link is for, e.g. a LianaMailer contact id put in by the
  snippet (#40). Only used to tell readers apart; it is never stored as such.
- signature: HMAC of the two, so nobody can make links for other readers.
- answer: the one-tap answer (added by the email block's buttons).

Newsletter snippet links (#40) are the same without the signature:

    {public_base_url}/r/{survey_token}?r=$id$&c={campaign}&seg={segment}&a={answer}

LianaMailer replaces the `$id$` placeholder with each contact's id when it sends,
so every reader still counts once. A pasted snippet is the same HTML for everyone
and LianaMailer cannot sign per reader, so these links are not signed: someone
who edits a link by hand can answer again under a made-up id. Only surveys whose
snippet was made accept them (surveys.newsletter_links); all others keep needing
the signature. Signed newsletter
links through the LianaMailer API are #118. c and seg are the campaign and
segment tags results are compared by.

The respondent service stores response_key() as responses.link_token_hash: the
same reader and survey always give the same key, so a second tap is not counted
twice, but the key cannot be turned back into the reader reference.
"""

import base64
import hashlib
import hmac
import re
from urllib.parse import urlencode

READER_REF = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
#: Campaign and segment tags: lower-case slugs, e.g. "member-nps-2026".
TAG = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?")


class LinkError(ValueError):
    """The link is not valid."""


def _mac(secret: str, *parts: str) -> str:
    digest = hmac.new(secret.encode(), "\x1f".join(parts).encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def signature(secret: str, survey_token: str, reader_ref: str) -> str:
    return _mac(secret, "answer-link", survey_token, reader_ref)[:32]


def response_key(secret: str, survey_token: str, reader_ref: str) -> str:
    """What is stored per response to stop double counting (not the reader ref)."""
    return _mac(secret, "response", survey_token, reader_ref)


def answer_link(base_url: str, secret: str, survey_token: str, reader_ref: str) -> str:
    """A reader's answer link, without the answer (the email buttons add &a=...)."""
    if not READER_REF.fullmatch(reader_ref):
        raise LinkError("reader references are 1-64 letters, digits or _ . : -")
    query = urlencode({"r": reader_ref, "s": signature(secret, survey_token, reader_ref)})
    return f"{base_url.rstrip('/')}/r/{survey_token}?{query}"


def check_signature(secret: str, survey_token: str, reader_ref: str, sig: str) -> None:
    """Raise LinkError unless the signature belongs to this survey and reader."""
    if not READER_REF.fullmatch(reader_ref or ""):
        raise LinkError("this link is not complete")
    expected = signature(secret, survey_token, reader_ref)
    if not hmac.compare_digest(expected, sig or ""):
        raise LinkError("this link is not valid")


def check_link(
    secret: str, survey_token: str, reader_ref: str, sig: str | None, *, unsigned_allowed: bool
) -> None:
    """Raise LinkError unless the link can be answered. A signed link must carry its
    reader's signature. A newsletter snippet link (no signature) is only accepted for
    surveys whose snippet was made (unsigned_allowed), and needs a reader reference
    that LianaMailer filled in (an unreplaced `$id$` is refused)."""
    if sig:
        check_signature(secret, survey_token, reader_ref, sig)
    elif not unsigned_allowed or not READER_REF.fullmatch(reader_ref or ""):
        raise LinkError("this link is not complete")


def snippet_link(
    base_url: str, survey_token: str, reader_tag: str, campaign: str, segment: str
) -> str:
    """The newsletter link for every reader, without the answer (the buttons add &a=...).

    reader_tag is LianaMailer's placeholder for the contact id and is left as it
    is, not URL-encoded, so LianaMailer can replace it."""
    for tag in (campaign, segment):
        if not TAG.fullmatch(tag):
            raise LinkError("tags are 1-40 lower-case letters, digits and -")
    query = urlencode({"c": campaign, "seg": segment})
    return f"{base_url.rstrip('/')}/r/{survey_token}?r={reader_tag}&{query}"
