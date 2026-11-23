"""Rules for contact requests. Plain Python, no SQL or HTTP."""

from typing import Literal

Status = Literal["new", "contacted", "done"]
STATUSES: tuple[Status, ...] = ("new", "contacted", "done")


def counts(rows: list[tuple[str, int]]) -> dict[str, int]:
    """Requests per status for the filter chips, with every status present and
    `all` as the total."""
    per_status = {status: 0 for status in STATUSES}
    for status, n in rows:
        per_status[status] = n
    return {"all": sum(per_status.values()), **per_status}
