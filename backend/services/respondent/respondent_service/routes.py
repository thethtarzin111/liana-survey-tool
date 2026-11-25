"""The answer link (#42): /r/<token>?r=<reader>&s=<signature>&a=<answer>.

The plain public link (/r/<token>, copied or from the QR code, with ?ch=link or
?ch=qr) shows the whole survey (#105). Its form posts back to the same address
with a visit key: a random reader id signed by this service, so the answers
count as one reader and can never be sent as someone's email reader id.

Newsletter snippet links (#40) come without the signature, with the reader id
LianaMailer filled in and campaign/segment tags: /r/<token>?r=<id>&c=..&seg=..&a=..
(see liana_survey_shared.links).

An answer link opens the follow-up page for the tapped answer, which saves the
answer itself with a POST (mail scanners only open links, so they never answer),
and offers the survey's other questions, "Tell us more" and "Contact me". Answers
go on the queue for the worker. An answer from a newsletter link is identified:
the LianaMailer contact id from the link goes with it (liana_survey_shared.contact)
and the page says so. Answers from the plain link and the QR code stay anonymous,
with only a key to count each reader once; a reader there who ticks "Contact me"
leaves an email address.
"""

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response

from liana_survey_shared import links
from liana_survey_shared.config import get_settings
from liana_survey_shared.contact import answer_contact_ref
from liana_survey_shared.messages import (
    AnswerSubmitted,
    AnswerValue,
    is_valid_campaign,
    is_valid_segment,
)
from liana_survey_shared.texts import text

from . import domain, pages, repo
from .answer_queue import AnswerQueue

log = logging.getLogger(__name__)
router = APIRouter()

#: Answer links carry a secret token: never cache them or pass them on.
PRIVATE = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex",
}
# Shown before the survey, and so its language, is known.
NOT_VALID = "This survey link is not valid."
#: Visit keys start with this, so they never match a reader id from an email link.
VISIT_PREFIX = "web-"
#: Largest form the survey link page can send: 20 questions of 5000 characters, and then some.
MAX_FORM_BYTES = 256 * 1024


def get_answer_queue(request: Request) -> AnswerQueue:
    """The process's queue publisher, made on first use. (Started on its own, the
    app also closes it on shutdown; inside the local gateway its lifespan does not
    run, so it cannot rely on it to create one.)"""
    state = request.app.state
    if getattr(state, "answer_queue", None) is None:
        state.answer_queue = AnswerQueue(get_settings().rabbitmq_url)
    return state.answer_queue


def _page(body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(body, status_code=status_code, headers=PRIVATE)


@router.get("/r/{link_token}", response_class=HTMLResponse)
async def answer(
    link_token: str,
    r: str | None = None,
    s: str | None = None,
    a: str | None = None,
    c: str | None = None,
    seg: str | None = None,
    ch: Literal["email", "link", "qr"] | None = None,
) -> HTMLResponse:
    """The plain link shows the whole survey. An answer link from an email shows the
    follow-up page for the tapped answer. Opening it saves nothing: mail scanners
    open every link in an email, and an answer must come from the reader. The page
    saves the answer itself (POST, step=tap); see pages.follow_up."""
    tenant_id = await run_in_threadpool(repo.tenant_for_token, link_token)
    if tenant_id is None:
        return _page(pages.problem(NOT_VALID), 404)
    survey = await run_in_threadpool(repo.survey_for_token, tenant_id, link_token)
    if survey is None:
        return _page(pages.problem(NOT_VALID), 404)
    channel = ch or ("email" if a is not None else "link")
    if r is None and s is None and a is None:
        await run_in_threadpool(repo.record_view, tenant_id, survey["id"], channel)
        return await _survey_page(tenant_id, survey, link_token, channel)
    fields = {"r": r or "", "s": s or "", "a": a or "", "ch": channel}
    if c is not None:
        fields["c"] = c
    if seg is not None:
        fields["seg"] = seg
    checked = await _checked_link(tenant_id, survey, link_token, fields)
    if isinstance(checked, HTMLResponse):
        return checked
    questions = await run_in_threadpool(repo.questions, tenant_id, survey["id"])
    return _page(_follow_up_page(survey, questions, checked, fields))


@dataclass(frozen=True)
class _LinkAnswer:
    """An answer link that passed every check."""

    value: int
    response_key: str
    answered: bool
    segment: str
    campaign: str | None


async def _checked_link(
    tenant_id: UUID, survey: dict, link_token: str, fields: dict[str, str]
) -> _LinkAnswer | HTMLResponse:
    """Check an answer link's fields (from the URL or the follow-up form): the
    reader and signature, the segment, that the survey takes the answer, and the
    answer itself. Returns the problem page when one fails."""
    settings = get_settings()
    language = survey["language"]
    reader = fields.get("r", "")
    try:
        links.check_link(
            settings.link_signing_secret,
            link_token,
            reader,
            fields.get("s") or None,
            unsigned_allowed=survey["newsletter_links"],
        )
    except links.LinkError:
        return _page(pages.problem(text("link_not_complete", language), language), 400)
    segment = fields.get("seg", "all")
    if not is_valid_segment(segment):
        return _page(pages.problem(text("link_not_complete", language), language), 400)
    # An unknown campaign tag is left out; it never stops the answer.
    campaign = fields.get("c") or None
    if campaign is not None and not is_valid_campaign(campaign):
        campaign = None
    # Not the reader reference itself: anonymous answers keep no link to the reader.
    response_key = links.response_key(settings.link_signing_secret, link_token, reader)
    answered = await run_in_threadpool(repo.answered_before, tenant_id, survey["id"], response_key)
    try:
        _survey_open(survey, answered)
        value = domain.one_tap_answer(survey["main_kind"], fields.get("a"))
    except domain.AnswerProblem as problem:
        return _page(pages.problem(problem.message(language), language), problem.status_code)
    return _LinkAnswer(value, response_key, answered, segment, campaign)


def _follow_up_page(
    survey: dict,
    questions: list[dict],
    checked: _LinkAnswer,
    fields: dict[str, str],
    sent: dict | None = None,
    error: str | None = None,
) -> str:
    return pages.follow_up(
        survey,
        questions[1:],
        answer=checked.value,
        link_fields=fields,
        comment_box=domain.shows_comment_box(survey, questions),
        contact_box=domain.shows_contact_me(survey),
        email_box=domain.asks_contact_email(answer_contact_ref(fields.get("r"))),
        identified=answer_contact_ref(fields.get("r")) is not None,
        sent=sent,
        error=error,
    )


async def _submit_link_answer(
    tenant_id: UUID, survey: dict, link_token: str, form: dict, queue: AnswerQueue
) -> Response:
    """The follow-up page's POST. step=tap saves the tapped answer alone (sent by
    the page's script as soon as it opens) and answers 204. Otherwise it is the
    whole form: the tapped answer, the other questions, the comment and "Contact
    me"; the thank-you page follows. Both replace any earlier answer of the reader
    (the same key), so the reader still counts once."""
    language = survey["language"]
    fields = {name: form[name][0] for name in ("r", "s", "a", "c", "seg", "ch") if form.get(name)}
    channel = fields.get("ch", "email")
    if channel not in ("email", "link", "qr"):
        channel = "email"
    fields["ch"] = channel
    checked = await _checked_link(tenant_id, survey, link_token, fields)
    if isinstance(checked, HTMLResponse):
        return checked
    tap = form.get("step", [""])[0] == "tap"
    main = AnswerValue(question_id=survey["main_id"], number=checked.value)
    # A newsletter link names its reader: the answer is identified, with or without
    # "Contact me", and the follow-up form never takes the contact away.
    contact_ref = answer_contact_ref(fields.get("r"))
    answers, comment, contact_me, contact_email = [main], None, False, None
    if not tap:
        questions = await run_in_threadpool(repo.questions, tenant_id, survey["id"])
        try:
            answers = domain.follow_up_answers(survey["type"], questions, form, checked.value)
            if domain.shows_comment_box(survey, questions):
                comment = domain.comment(form)
            contact_me, contact_email = domain.contact_request(survey, form, contact_ref)
        except domain.AnswerProblem as problem:
            again = _follow_up_page(
                survey, questions, checked, fields, sent=form, error=problem.message(language)
            )
            return _page(again, problem.status_code)
    # A reader's later taps change their answer, not the reach: count their first only.
    if not checked.answered:
        await run_in_threadpool(repo.record_view, tenant_id, survey["id"], channel)
    message = AnswerSubmitted(
        tenant_id=tenant_id,
        survey_id=survey["id"],
        link_token_hash=checked.response_key,
        channel=channel,
        segment=checked.segment,
        answers=answers,
        contact_ref=contact_ref,
        comment=comment,
        contact_me=contact_me,
        contact_email=contact_email,
        campaign=checked.campaign,
        main_only=tap,
    )
    try:
        await queue.publish(message)
    except Exception:
        log.exception("could not queue answer for survey %s", survey["id"])
        return _page(pages.problem(text("try_again", language), language), 503)
    if tap:
        return Response(status_code=204, headers=PRIVATE)
    return _page(
        pages.thank_you(
            survey["thank_you"], survey["accent_color"], survey["background_color"], language
        )
    )


def _visit_key(link_token: str) -> str:
    """A new reader id for this visit, with this service's signature."""
    reader = VISIT_PREFIX + secrets.token_urlsafe(16)
    signature = links.signature(get_settings().link_signing_secret, link_token, reader)
    return f"{reader}.{signature}"


def _check_visit_key(link_token: str, key: str) -> str:
    """The reader id in a visit key from _visit_key(). Raises links.LinkError."""
    reader, _, signature = key.partition(".")
    if not reader.startswith(VISIT_PREFIX) or not signature:
        raise links.LinkError("not a visit key")
    links.check_signature(get_settings().link_signing_secret, link_token, reader, signature)
    return reader


def _survey_open(survey: dict, answered: bool) -> None:
    """Raises AnswerProblem unless the survey takes this reader's answers now."""
    full = domain.limit_reached(survey["response_limit"], survey["response_count"]) and not answered
    domain.check_open(
        survey["status"], closes_at=survey["closes_at"], now=datetime.now(UTC), full=full
    )


async def _survey_page(tenant_id, survey: dict, link_token: str, channel: str) -> HTMLResponse:
    language = survey["language"]
    try:
        _survey_open(survey, answered=False)
    except domain.AnswerProblem as problem:
        return _page(pages.problem(problem.message(language), language), problem.status_code)
    questions = await run_in_threadpool(repo.questions, tenant_id, survey["id"])
    if not questions:
        return _page(pages.problem(text("not_open", language), language), 403)
    form = pages.survey_form(
        survey,
        questions,
        key=_visit_key(link_token),
        channel=channel,
        comment_box=domain.shows_comment_box(survey, questions),
        contact_box=domain.shows_contact_me(survey),
    )
    return _page(form)


@router.post("/r/{link_token}", response_class=HTMLResponse)
async def submit(
    link_token: str, request: Request, queue: AnswerQueue = Depends(get_answer_queue)
) -> HTMLResponse:
    """Take the answers sent from the survey link page or from the follow-up page of
    an answer link, and show the thank-you page."""
    settings = get_settings()
    tenant_id = await run_in_threadpool(repo.tenant_for_token, link_token)
    if tenant_id is None:
        return _page(pages.problem(NOT_VALID), 404)
    survey = await run_in_threadpool(repo.survey_for_token, tenant_id, link_token)
    if survey is None:
        return _page(pages.problem(NOT_VALID), 404)
    language = survey["language"]

    body = await request.body()
    if len(body) > MAX_FORM_BYTES:
        return _page(pages.problem(text("answer_not_valid", language), language), 413)
    try:
        form = parse_qs(body.decode("utf-8"), keep_blank_values=True, max_num_fields=500)
    except (UnicodeDecodeError, ValueError):
        return _page(pages.problem(text("link_not_complete", language), language), 400)
    if "key" not in form and "a" in form:
        return await _submit_link_answer(tenant_id, survey, link_token, form, queue)
    try:
        key = form.get("key", [""])[0]
        reader = _check_visit_key(link_token, key)
    except links.LinkError:
        return _page(pages.problem(text("link_not_complete", language), language), 400)
    channel = form.get("ch", ["link"])[0]
    if channel not in ("link", "qr"):
        channel = "link"

    response_key = links.response_key(settings.link_signing_secret, link_token, reader)
    answered = await run_in_threadpool(repo.answered_before, tenant_id, survey["id"], response_key)
    try:
        _survey_open(survey, answered)
    except domain.AnswerProblem as problem:
        return _page(pages.problem(problem.message(language), language), problem.status_code)
    questions = await run_in_threadpool(repo.questions, tenant_id, survey["id"])
    comment_box = domain.shows_comment_box(survey, questions)
    try:
        answers = domain.form_answers(survey["type"], questions, form)
        comment = domain.comment(form) if comment_box else None
        # No contact id here: "Contact me" needs the address the reader types.
        contact_me, contact_email = domain.contact_request(survey, form, None)
    except domain.AnswerProblem as problem:
        again = pages.survey_form(
            survey,
            questions,
            key=key,
            channel=channel,
            sent=form,
            error=problem.message(language),
            comment_box=comment_box,
            contact_box=domain.shows_contact_me(survey),
        )
        return _page(again, problem.status_code)
    thanks = pages.thank_you(
        survey["thank_you"], survey["accent_color"], survey["background_color"], language
    )
    # Every question is optional and left blank: nothing to save, and no response counted.
    if not answers and comment is None and not contact_me:
        return _page(thanks)

    message = AnswerSubmitted(
        tenant_id=tenant_id,
        survey_id=survey["id"],
        link_token_hash=response_key,
        channel=channel,
        answers=answers,
        comment=comment,
        contact_me=contact_me,
        contact_email=contact_email,
    )
    try:
        await queue.publish(message)
    except Exception:
        log.exception("could not queue answers for survey %s", survey["id"])
        return _page(pages.problem(text("try_again", language), language), 503)
    return _page(thanks)
