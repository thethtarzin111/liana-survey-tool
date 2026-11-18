"""The answer link (#42): /r/<token>?r=<reader>&s=<signature>&a=<answer>.

Newsletter snippet links (#40) come without the signature, with the reader id
LianaMailer filled in and campaign/segment tags: /r/<token>?r=<id>&c=..&seg=..&a=..
(see liana_survey_shared.links).

Records the one-tap answer to the survey's main question by putting it on the
queue, and shows a plain thank-you page. Answers stay anonymous: only a key
derived from the reader reference is stored, to count each reader once.
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse

from liana_survey_shared import links
from liana_survey_shared.config import get_settings
from liana_survey_shared.messages import AnswerSubmitted, AnswerValue

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
NOT_VALID = "This survey link is not valid."
NOT_COMPLETE = "This link is not complete or not valid. Open it again from your email."
TRY_AGAIN = "We couldn’t save your answer right now. Please open the link again in a moment."


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
    queue: AnswerQueue = Depends(get_answer_queue),
) -> HTMLResponse:
    """Record a one-tap answer from the email and show the thank-you page."""
    settings = get_settings()
    tenant_id = await run_in_threadpool(repo.tenant_for_token, link_token)
    if tenant_id is None:
        return _page(pages.problem(NOT_VALID), 404)
    try:
        links.check_link(settings.link_signing_secret, link_token, r or "", s)
    except links.LinkError:
        return _page(pages.problem(NOT_COMPLETE), 400)

    survey = await run_in_threadpool(repo.survey_for_token, tenant_id, link_token)
    if survey is None:
        return _page(pages.problem(NOT_VALID), 404)
    try:
        domain.check_open(survey["status"])
        value = domain.one_tap_answer(survey["main_kind"], a)
    except domain.AnswerProblem as problem:
        return _page(pages.problem(str(problem)), problem.status_code)

    message = AnswerSubmitted(
        tenant_id=tenant_id,
        survey_id=survey["id"],
        # Not the reader reference itself: anonymous answers keep no link to the reader.
        link_token_hash=links.response_key(settings.link_signing_secret, link_token, r or ""),
        answers=[AnswerValue(question_id=survey["main_id"], number=value)],
    )
    try:
        await queue.publish(message)
    except Exception:
        log.exception("could not queue answer for survey %s", survey["id"])
        return _page(pages.problem(TRY_AGAIN), 503)

    return _page(
        pages.thank_you(survey["thank_you"], survey["accent_color"], survey["background_color"])
    )
