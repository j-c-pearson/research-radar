from __future__ import annotations

import re
import unicodedata

from litreview.models import MatchedPaper

TRAILING_PUNCTUATION = ".,;:!?)]}'\""


def normalize_doi(doi: str) -> str:
    return doi.strip().removeprefix("https://doi.org/").removeprefix("http://doi.org/").lower()


def clean_title(title: str) -> str:
    value = unicodedata.normalize("NFKC", title).lower().strip()
    value = value.replace("–", "-").replace("—", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    value = re.sub(r"\s+", " ", value)
    return value.rstrip(TRAILING_PUNCTUATION).strip()


def dedupe_papers(papers: list[MatchedPaper]) -> list[MatchedPaper]:
    deduped: list[MatchedPaper] = []
    by_identifier: dict[tuple[str, str], MatchedPaper] = {}
    by_title: dict[str, MatchedPaper] = {}

    for paper in papers:
        identifier_key = _identifier_key(paper)
        title_key = clean_title(paper.record.title)
        existing = by_title.get(title_key)
        if existing is None and identifier_key is not None:
            existing = by_identifier.get(identifier_key)

        if existing is not None:
            _merge(existing, paper)
        else:
            paper.sources = sorted(set(paper.sources or [paper.record.source]))
            if identifier_key is not None:
                by_identifier[identifier_key] = paper
            by_title[title_key] = paper
            deduped.append(paper)

    return deduped


def _identifier_key(paper: MatchedPaper) -> tuple[str, str] | None:
    if paper.record.doi:
        return ("doi", normalize_doi(paper.record.doi))
    if paper.record.preprint_id:
        return ("preprint", paper.record.preprint_id.strip().lower())
    return None


def _merge(existing: MatchedPaper, duplicate: MatchedPaper) -> None:
    existing.sources = sorted(set([*existing.sources, duplicate.record.source, *duplicate.sources]))
    existing.duplicate_record_ids.append(f"{duplicate.record.source}:{duplicate.record.source_id}")
    existing.match.matched_topic_ids = sorted(
        set([*existing.match.matched_topic_ids, *duplicate.match.matched_topic_ids])
    )
    existing.match.matched_watch_item_ids = sorted(
        set([*existing.match.matched_watch_item_ids, *duplicate.match.matched_watch_item_ids])
    )
    if not existing.record.abstract and duplicate.record.abstract:
        existing.record.abstract = duplicate.record.abstract
    if not existing.record.doi and duplicate.record.doi:
        existing.record.doi = duplicate.record.doi
