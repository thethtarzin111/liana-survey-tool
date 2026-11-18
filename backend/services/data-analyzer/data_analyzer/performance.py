"""Survey performance calculations shared by the endpoint and unit tests."""

from decimal import ROUND_HALF_UP, Decimal


def response_rate(responses: int, views: int) -> int | None:
    """Responses as a whole percentage of views, or None when nothing was viewed."""
    if views <= 0:
        return None
    return int((Decimal(responses) * 100 / Decimal(views)).quantize(Decimal(1), ROUND_HALF_UP))
