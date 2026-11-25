"""The two AI steps of comment insights, as ports. Adapters live in `adapters.py`.

Both only ever see redacted comment text and short ids ("C1"), never response ids,
contact references or scores."""

from typing import Protocol


class CommentGrouper(Protocol):
    """Steps 4 and 5: turn comments into vectors and group the similar ones."""

    #: Shown in the run details, e.g. "Multilingual embeddings + HDBSCAN".
    name: str

    def group(self, texts: list[str]) -> list[int]:
        """One group number per text, in the same order. -1 means the text fits no group."""
        ...


class ThemeWriter(Protocol):
    """Step 6: the LLM. Reads one batch of comments and names a theme for each."""

    #: Shown in the run details, e.g. "Mock (no LLM connected)".
    name: str

    def describe(self, comments: list[dict[str, str]], known_themes: list[str]) -> list[dict]:
        """`comments` are {"comment_id", "text"}. Returns one item per comment:

            {"comment_id": "C1", "theme": "Slow customer support", "sentiment": "negative",
             "summary": "The customer is unhappy with slow replies.",
             "quote": "takes too long to reply"}

        `known_themes` are names to reuse when a comment fits one (the survey's reasons).
        The result is checked in code: unknown ids are dropped and every quote must be
        found word-for-word in its comment."""
        ...
