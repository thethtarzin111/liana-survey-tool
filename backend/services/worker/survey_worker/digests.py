"""When to email a survey's owner about new responses (rules in domain.py).

Two paths claim an email, both through claim_digest():
- right after the worker saves a new response, in the same transaction;
- the periodic sweep, for responses that were held within the interval.

Claiming locks the survey's response_notifications row and records the email
as sent before the message is published, so two workers never send the same
digest. A digest that then fails to publish is lost; later responses are still
emailed.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from uuid import UUID

import psycopg

from liana_survey_shared.config import get_settings
from liana_survey_shared.db import due_response_digests, tenant_connection
from liana_survey_shared.messages import Message, NewResponsesDigest

from . import domain

log = logging.getLogger(__name__)

Publish = Callable[[Message], Awaitable[None]]


def claim_digest(
    conn: psycopg.Connection,
    survey_id: UUID,
    *,
    after_new_response: bool = False,
    interval: timedelta | None = None,
    app_base_url: str | None = None,
) -> NewResponsesDigest | None:
    """The email to send now for this survey, recorded as sent; None if none is due.

    After a new response, a survey that has no row yet gets one whose baseline
    is the total before that response, so its first email goes out at once.
    Turning notify_on_response off removes the row: held responses are not sent."""
    settings = get_settings()
    if interval is None:
        interval = timedelta(seconds=settings.response_digest_interval_seconds)
    survey = conn.execute(
        """select s.tenant_id, s.title, s.notify_on_response, u.email, u.name
           from surveys s left join users u on u.id = s.created_by
           where s.id = %s""",
        (survey_id,),
    ).fetchone()
    if survey is None:
        return None
    tenant_id, title, notify, email, name = survey
    if not notify:
        conn.execute("delete from response_notifications where survey_id = %s", (survey_id,))
        return None
    if email is None:
        return None
    if after_new_response:
        conn.execute(
            """insert into response_notifications (survey_id, tenant_id, notified_count)
               select survey_id, tenant_id, greatest(response_count - 1, 0)
               from survey_aggregates where survey_id = %s
               on conflict (survey_id) do nothing""",
            (survey_id,),
        )
    state = conn.execute(
        """select last_sent_at, notified_count, now() from response_notifications
           where survey_id = %s for update""",
        (survey_id,),
    ).fetchone()
    if state is None:
        return None
    last_sent_at, notified_count, now = state
    # Read after the lock, so the total includes every response saved before it.
    total = conn.execute(
        "select coalesce(max(response_count), 0) from survey_aggregates where survey_id = %s",
        (survey_id,),
    ).fetchone()[0]
    new = domain.new_responses_due(
        total=total,
        notified_count=notified_count,
        last_sent_at=last_sent_at,
        now=now,
        interval=interval,
    )
    if new == 0:
        return None
    conn.execute(
        """update response_notifications set last_sent_at = %s, notified_count = %s
           where survey_id = %s""",
        (now, total, survey_id),
    )
    return domain.digest(
        tenant_id=tenant_id,
        survey_id=survey_id,
        survey_title=title,
        new_responses=new,
        total_responses=total,
        app_base_url=app_base_url or settings.app_base_url,
        recipient_email=email,
        recipient_name=name,
    )


def claim_due(
    tenant_id: UUID, survey_id: UUID, interval: timedelta | None = None
) -> NewResponsesDigest | None:
    with tenant_connection(tenant_id) as conn:
        return claim_digest(conn, survey_id, interval=interval)


async def sweep_once(publish: Publish, interval: timedelta | None = None) -> int:
    """Claim and publish every due digest. Returns how many were published."""
    if interval is None:
        interval = timedelta(seconds=get_settings().response_digest_interval_seconds)
    due = await asyncio.to_thread(due_response_digests, int(interval.total_seconds()))
    sent = 0
    for survey_id, tenant_id in due:
        message = await asyncio.to_thread(claim_due, tenant_id, survey_id, interval)
        if message is not None:
            await publish(message)
            sent += 1
    return sent


async def sweep_forever(publish: Publish, every_seconds: float | None = None) -> None:
    """Run sweep_once() every `every_seconds` until cancelled. Errors are logged
    and the next sweep tries again."""
    if every_seconds is None:
        every_seconds = get_settings().response_digest_sweep_seconds
    while True:
        await asyncio.sleep(every_seconds)
        try:
            sent = await sweep_once(publish)
        except Exception:
            log.exception("response digest sweep failed, trying again later")
        else:
            if sent:
                log.info("response digests sent: %s", sent)
