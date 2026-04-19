from __future__ import annotations

from collections import Counter
from typing import Iterable


STOPWORDS = {
    "der", "die", "das", "und", "oder", "ein", "eine", "zu", "mit", "von", "im", "in", "auf", "für", "am",
    "wie", "wann", "welche", "welcher", "welches", "ist", "sind", "ich", "wir", "du", "ihr", "den", "dem",
}


def _tokenize(text: str) -> list[str]:
    tokens = [t.strip(" ,.;:!?()[]{}\n\t").lower() for t in text.split()]
    return [t for t in tokens if t and t not in STOPWORDS]


def rank_texts(query: str, docs: Iterable[dict[str, str]], top_k: int = 3) -> list[dict[str, str]]:
    query_terms = Counter(_tokenize(query))
    scored: list[tuple[int, dict[str, str]]] = []
    for doc in docs:
        text = f"{doc.get('title', '')} {doc.get('text', '')}"
        terms = Counter(_tokenize(text))
        score = sum(min(query_terms[t], terms[t]) for t in query_terms)
        scored.append((score, doc))
    ranked = [doc for score, doc in sorted(scored, key=lambda x: x[0], reverse=True) if score > 0]
    return ranked[:top_k]