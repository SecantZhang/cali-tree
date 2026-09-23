"""Keyword-match retrieval of a similar real human-annotation note, for grounding the
human-proxy debate agent (the "hybrid persona + optional retrieval" design).

No embeddings/vector DB — the repo doesn't have that infra yet (``docs/architecture.md``
scopes it as future systems-design work), and the annotation corpus is small (~287
files), so a linear keyword scan is sufficient for v1. A future embedding-based
retriever can replace the body of ``find_similar_human_note`` without touching callers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional

from ....database.dl_human_annotations.loader import (
    HumanAnnotationRecord,
    load_human_annotations,
)

# Small per-metric keyword lists used to score free-text annotation notes for relevance.
_METRIC_KEYWORDS: dict[str, set[str]] = {
    "M1": {"assembly", "plan", "prompt", "notes", "goal"},
    "M2": {"render", "broken", "black", "corrupt", "glitch", "crash"},
    "M3": {"completeness", "missing", "prompt", "aspect", "incomplete"},
    "M4": {"visual", "alignment", "broll", "aroll", "cut", "timing", "screen"},
    "M5": {"pacing", "flow", "transition", "coherence", "watchability", "smooth"},
    "M6": {"audio", "voiceover", "sync", "pause", "freeze", "cutoff", "interruption"},
}

_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass
class RetrievedNote:
    text: str
    source_path: str
    item_id: str  # the OTHER item this note came from, never the item being debated
    matched_terms: list[str]


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _candidate_texts(annotation: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    other = annotation.get("other_anomalies")
    if isinstance(other, str) and other.strip():
        texts.append(other.strip())
    for key, val in annotation.items():
        if key.endswith("_note") and isinstance(val, str) and val.strip():
            texts.append(val.strip())
    return texts


@lru_cache(maxsize=32)
def _load_records_cached(project: str) -> tuple[HumanAnnotationRecord, ...]:
    return tuple(load_human_annotations(projects=[project]))


def find_similar_human_note(
    *,
    sample: dict[str, Any],
    metric_id: str,
    records: Optional[list[HumanAnnotationRecord]] = None,
    exclude_item_id: Optional[str] = None,
) -> Optional[RetrievedNote]:
    """Best-effort lookup of a similar real human note; ``None`` if nothing qualifies.

    ``exclude_item_id`` defaults to ``sample``'s own item id so a debate never grounds
    itself in the exact human label it may later be compared against (mirrors
    CLAUDE.md's "always trained on data disjoint from held-out test set", applied here
    at the per-item level).
    """
    project = sample.get("project", "")
    prompt_idx = sample.get("prompt_idx", "")
    model = sample.get("model", "")
    self_item_id = exclude_item_id
    if self_item_id is None:
        self_item_id = sample.get("item_id") or f"{project}::{prompt_idx}::{model}"

    pool = records if records is not None else list(_load_records_cached(project))
    keywords = _METRIC_KEYWORDS.get(metric_id, set())

    best: Optional[RetrievedNote] = None
    best_score = 0
    for record in pool:
        if record.item_id == self_item_id:
            continue
        for text in _candidate_texts(record.annotation):
            matched = sorted(_tokenize(text) & keywords)
            if len(matched) > best_score:
                best_score = len(matched)
                best = RetrievedNote(
                    text=text,
                    source_path=record.path,
                    item_id=record.item_id,
                    matched_terms=matched,
                )

    return best if best_score >= 1 else None
