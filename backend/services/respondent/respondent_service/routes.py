"""The answer link (#42): /r/<token>?r=<reader>&s=<signature>&a=<answer>.

Newsletter snippet links (#40) come without the signature, with the reader id
LianaMailer filled in and campaign/segment tags: /r/<token>?r=<id>&c=..&seg=..&a=..
(see liana_survey_shared.links).

Records the one-tap answer to the survey's main question by putting it on the
queue, and shows a plain thank-you page. Answers stay anonymous: only a key
derived from the reader reference is stored, to count each reader once.
"""

import logging
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse

from liana_survey_shared import links
from liana_survey_shared.config import get_settings
from liana_survey_shared.messages import AnswerSubmitted, AnswerValue
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
FROM_EMAIL = "For now, this survey is answered from the email it came in: tap an answer there."


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
    if r is None and s is None and a is None:
        await run_in_threadpool(repo.record_view, tenant_id, survey["id"], channel)
        # The full public survey page is #105; this valid visit still belongs in performance.
        return _page(pages.page("Answer from your email", FROM_EMAIL), 400)
    language = survey["language"]
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
