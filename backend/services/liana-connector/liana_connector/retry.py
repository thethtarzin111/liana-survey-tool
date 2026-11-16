"""Retry timing for calls to Liana."""

MAX_ATTEMPTS = 8


def backoff_seconds(attempt: int, base: float = 2.0, cap: float = 300.0) -> float:
    """Exponential back-off: 2, 4, 8, ... seconds, never more than `cap`.
    `attempt` starts at 1."""
    if attempt < 1:
        raise ValueError("attempt starts at 1")
    return min(cap, base**attempt)
