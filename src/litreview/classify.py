from __future__ import annotations

import re

from litreview.models import MatchInfo, MatchedPaper, PaperRecord, Priority, Registry, RelevanceLabel, Topic

PRIORITY_RANK = {Priority.high: 0, Priority.medium: 1, Priority.low: 2}


def classify_record(
    record: PaperRecord,
    registry: Registry,
    matched_topic_ids: set[str] | None = None,
    matched_watch_item_ids: set[str] | None = None,
) -> MatchedPaper | None:
    infer_topics = matched_topic_ids is None
    infer_watch_items = matched_watch_item_ids is None
    matched_topic_ids = set(matched_topic_ids or [])
    matched_watch_item_ids = set(matched_watch_item_ids or [])

    if infer_topics:
        matched_topic_ids.update(_topics_matching_record_text(record, registry))

    if infer_watch_items:
        matched_watch_item_ids.update(_watch_items_matching_record(record, registry))

    if not matched_topic_ids and not matched_watch_item_ids:
        return None

    topic = _primary_topic(matched_topic_ids, registry)
    category = topic.category if topic else ""
    subcategory = topic.subcategory if topic else ""

    if matched_topic_ids and matched_watch_item_ids:
        relevance = RelevanceLabel.high
    elif matched_watch_item_ids:
        relevance = RelevanceLabel.medium
    else:
        relevance = RelevanceLabel.low

    return MatchedPaper(
        record=record,
        match=MatchInfo(
            matched_topic_ids=sorted(matched_topic_ids),
            matched_watch_item_ids=sorted(matched_watch_item_ids),
            category=category,
            subcategory=subcategory,
            relevance_label=relevance,
        ),
        sources=[record.source],
    )


def _topics_matching_record_text(record: PaperRecord, registry: Registry) -> set[str]:
    text = f"{record.title}\n{record.abstract}".lower()
    matches = set()
    for topic in registry.topics:
        if any(_contains_term(text, term) for term in topic.query_terms):
            matches.add(topic.id)
    return matches


def _watch_items_matching_record(record: PaperRecord, registry: Registry) -> set[str]:
    author_text = "\n".join(record.authors).lower()
    matches = set()
    for item in registry.watchlist:
        names = [item.name, *item.aliases]
        if any(name and name.lower() in author_text for name in names):
            matches.add(item.id)
    return matches


def _primary_topic(topic_ids: set[str], registry: Registry) -> Topic | None:
    topics = [topic for topic in registry.topics if topic.id in topic_ids]
    if not topics:
        return None
    return sorted(topics, key=lambda topic: (PRIORITY_RANK[topic.priority], registry.topics.index(topic)))[0]


def _contains_term(text: str, term: str) -> bool:
    term = term.strip().lower()
    if not term:
        return False
    if " " in term:
        return term in text
    return re.search(rf"\b{re.escape(term)}\b", text) is not None
