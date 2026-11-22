"""The answer link (#42): /r/<token>?r=<reader>&s=<signature>&a=<answer>.

The plain public link (/r/<token>, copied or from the QR code, with ?ch=link or
?ch=qr) shows the whole survey (#105). Its form posts back to the same address
with a visit key: a random reader id signed by this service, so the answers
count as one reader and can never be sent as someone's email reader id.

Newsletter snippet links (#40) come without the signature, with the reader id
LianaMailer filled in and campaign/segment tags: /r/<token>?r=<id>&c=..&seg=..&a=..
(see liana_survey_shared.links).

Records the one-tap answer to the survey's main question by putting it on the
queue, and shows a plain thank-you page. Answers stay anonymous: only a key
derived from the reader reference is stored, to count each reader once.
"""

import logging
import secrets
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse

from liana_survey_shared import links
from liana_survey_shared.config import get_settings
from liana_survey_shared.messages import AnswerSubmitted, AnswerValue, is_valid_segment
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
    seg: str | None = None,
    ch: Literal["email", "link", "qr"] | None = None,
    queue: AnswerQueue = Depends(get_answer_queue),
) -> HTMLResponse:
    """Record a one-tap answer from the email and show the thank-you page."""
    settings = get_settings()
    tenant_id = await run_in_threadpool(repo.tenant_for_token, link_token)
    if tenant_id is None:
        return _page(pages.problem(NOT_VALID), 404)
    survey = await run_in_threadpool(repo.survey_for_token, tenant_id, link_token)
    if survey is None:
        return _page(pages.problem(NOT_VALID), 404)
    channel = ch or ("email" if a is not None else "link")
    language = survey["language"]
    if r is None and s is None and a is None:
        await run_in_threadpool(repo.record_view, tenant_id, survey["id"], channel)
        return await _survey_page(tenant_id, survey, link_token, channel)
    try:
        links.check_link(
            settings.link_signing_secret,
            link_token,
            r or "",
            s,
            unsigned_allowed=survey["newsletter_links"],
        )
    except links.LinkError:
        return _page(pages.problem(text("link_not_complete", language), language), 400)
    segment = "all" if seg is None else seg
    if not is_valid_segment(segment):
        return _page(pages.problem(text("link_not_complete", language), language), 400)
    # Not the reader reference itself: anonymous answers keep no link to the reader.
    response_key = links.response_key(settings.link_signing_secret, link_token, r or "")
    answered = await run_in_threadpool(repo.answered_before, tenant_id, survey["id"], response_key)
    full = domain.limit_reached(survey["response_limit"], survey["response_count"]) and not answered
    try:
        domain.check_open(
            survey["status"], closes_at=survey["closes_at"], now=datetime.now(UTC), full=full
        )
        value = domain.one_tap_answer(survey["main_kind"], a)
    except domain.AnswerProblem as problem:
        return _page(pages.problem(problem.message(language), language), problem.status_code)

    # A reader's later taps change their answer, not the reach: count their first only.
    if not answered:
        await run_in_threadpool(repo.record_view, tenant_id, survey["id"], channel)

    message = AnswerSubmitted(
        tenant_id=tenant_id,
        survey_id=survey["id"],
        link_token_hash=response_key,
        channel=channel,
        segment=segment,
        answers=[AnswerValue(question_id=survey["main_id"], number=value)],
    )
    try:
        await queue.publish(message)
    except Exception:
        log.exception("could not queue answer for survey %s", survey["id"])
        return _page(pages.problem(text("try_again", language), language), 503)

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
    form = pages.survey_form(survey, questions, key=_visit_key(link_token), channel=channel)
    return _page(form)


@router.post("/r/{link_token}", response_class=HTMLResponse)
async def submit(
    link_token: str, request: Request, queue: AnswerQueue = Depends(get_answer_queue)
) -> HTMLResponse:
    """Take the answers sent from the survey link page and show the thank-you page."""
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
        key = form.get("key", [""])[0]
        reader = _check_visit_key(link_token, key)
    except (UnicodeDecodeError, ValueError, links.LinkError):
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
    try:
        answers = domain.form_answers(survey["type"], questions, form)
    except domain.AnswerProblem as problem:
        again = pages.survey_form(
            survey,
            questions,
            key=key,
            channel=channel,
            sent=form,
            error=problem.message(language),
        )
        return _page(again, problem.status_code)

    message = AnswerSubmitted(
        tenant_id=tenant_id,
        survey_id=survey["id"],
        link_token_hash=response_key,
        channel=channel,
        answers=answers,
    )
    try:
        await queue.publish(message)
    except Exception:
        log.exception("could not queue answers for survey %s", survey["id"])
        return _page(pages.problem(text("try_again", language), language), 503)
    return _page(
        pages.thank_you(
            survey["thank_you"], survey["accent_color"], survey["background_color"], language
        )
    )
