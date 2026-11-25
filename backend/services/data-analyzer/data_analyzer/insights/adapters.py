"""Adapters for the comment insights ports, picked with INSIGHTS_GROUPER and
INSIGHTS_WRITER. `mock` is the default for both and needs no model or network.

`hdbscan` needs the optional AI packages: pip install -e "backend/services/data-analyzer[ai]".
There is no real LLM adapter yet: which LLM (and where it is hosted) is Liana's
decision, see docs/gdpr.md."""

import re
from typing import Any

from liana_survey_shared.config import Settings

from .ports import CommentGrouper, ThemeWriter

# The mock's topics: a theme name and word beginnings in English, Finnish and Swedish.
_TOPICS = {
    "Events": "event meetup fair evening atmospher tapahtum ilta tillställ",
    "Price": "price fee cost expensive worth cheap hinta maksu kallis pris avgift",
    "Communication": "communicat news email mail information summary uutis viest tiedo nyhet",
    "Website": "website site online login verkko sivu webb",
    "Staff and support": "helpful coordinator staff teacher support counsel help henkilö opettaja "
    "tuki personal lärare",
    "Content": "content material slide stories photo exercise practical sisält materiaali innehåll",
    "Length and layout": "long short layout phone screen read pitkä lyhyt puhelin lång",
    "Schedule": "schedule late time date book queue pace aikataulu myöhä jono schema",
    "Community": "community friendly involved group volunteer yhteisö ryhmä gemenskap",
    "Facilities": "room warm space campus tila kampus lokal",
}
_WORD = re.compile(r"[^\W\d_]+")


def _topic(text: str) -> str | None:
    """The mock topic whose words the text uses most, None when it uses none."""
    words = _WORD.findall(text.lower())
    hits = {
        topic: sum(any(w.startswith(stem) for stem in stems.split()) for w in words)
        for topic, stems in _TOPICS.items()
    }
    best = max(hits, key=lambda topic: hits[topic])
    return best if hits[best] else None


class MockGrouper:
    """Puts every comment in one group, so the mock writer does all the work."""

    name = "Mock (one group)"

    def group(self, texts: list[str]) -> list[int]:
        return [0] * len(texts)


class MockThemeWriter:
    """Stands in for the LLM with a fixed word list, so the tab works without one.

    A comment's theme is the topic whose words it uses most, named like the survey's
    reason for that topic when there is one. Comments with no topic are "Other". The
    quote is the comment's first words, so it is found word-for-word. Mixed scores get
    "neutral"; a real LLM would read them."""

    name = "Mock (no LLM connected)"

    def describe(self, comments: list[dict[str, str]], known_themes: list[str]) -> list[dict]:
        known = {_topic(theme): theme for theme in reversed(known_themes) if _topic(theme)}
        items: list[dict[str, Any]] = []
        for comment in comments:
            topic = _topic(comment["text"])
            items.append(
                {
                    "comment_id": comment["comment_id"],
                    "theme": known.get(topic, topic) if topic else "Other",
                    "sentiment": "neutral",
                    "summary": f"The comment is about {topic.lower()}." if topic else "",
                    "quote": " ".join(comment["text"].split()[:8]),
                }
            )
        return items


def cluster(vectors: Any, min_cluster_size: int = 5) -> list[int]:
    """HDBSCAN labels of the vectors (-1 for noise). It finds the number of groups itself."""
    from sklearn.cluster import HDBSCAN

    return [int(label) for label in HDBSCAN(min_cluster_size=min_cluster_size).fit_predict(vectors)]


class HdbscanGrouper:
    """Multilingual sentence embeddings (Finnish, Swedish and English alike), then HDBSCAN."""

    name = "Multilingual embeddings + HDBSCAN"

    def __init__(self, model: str = "paraphrase-multilingual-MiniLM-L12-v2") -> None:
        self._model_name = model
        self._model = None

    def group(self, texts: list[str]) -> list[int]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return cluster(vectors, min_cluster_size=max(5, len(texts) // 50))


def build_grouper(settings: Settings) -> CommentGrouper:
    """Pick the grouper from INSIGHTS_GROUPER."""
    if settings.insights_grouper == "mock":
        return MockGrouper()
    if settings.insights_grouper == "hdbscan":
        return HdbscanGrouper()
    raise ValueError(f"Unknown INSIGHTS_GROUPER: {settings.insights_grouper}")


def build_writer(settings: Settings) -> ThemeWriter:
    """Pick the theme writer from INSIGHTS_WRITER. Only the mock exists yet."""
    if settings.insights_writer == "mock":
        return MockThemeWriter()
    raise ValueError(f"Unknown INSIGHTS_WRITER: {settings.insights_writer}")
