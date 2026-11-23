"""Rules for contact requests. Plain Python, no SQL or HTTP."""

from typing import Literal

Status = Literal["new", "contacted", "done"]
STATUSES: tuple[Status, ...] = ("new", "contacted", "done")
ReplyStatus = Literal["pending", "sent", "failed"]


class AlreadyResolved(Exception):
    """The reader has been told, or is being told, already."""


def check_can_resolve(reply_status: ReplyStatus | None) -> None:
    """A request is resolved once: the reader gets one "You said, we did"
    message. Only a message that failed to go out may be sent again."""
    if reply_status in ("pending", "sent"):
        raise AlreadyResolved("This request is resolved and the reader has been told.")


def counts(rows: list[tuple[str, int]]) -> dict[str, int]:
    """Requests per status for the filter chips, with every status present and
    `all` as the total."""
    per_status = {status: 0 for status in STATUSES}
    for status, n in rows:
        per_status[status] = n
    return {"all": sum(per_status.values()), **per_status}
