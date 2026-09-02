from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import httpx

from litreview.models import DateWindow, PaperRecord


@dataclass
class RetrievedPaper:
    record: PaperRecord
    matched_topic_ids: set[str] = field(default_factory=set)
    matched_watch_item_ids: set[str] = field(default_factory=set)


class SourceAdapter:
    source_id: str
    api_url: str

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=10.0, follow_redirects=True)

    def search(
        self, query: str, window: DateWindow, max_results: int = 10
    ) -> list[PaperRecord]:
        raise NotImplementedError

    def search_author(
        self,
        author: str,
        window: DateWindow,
        max_results: int = 10,
        source_id: str = "",
        orcid: str = "",
    ) -> list[PaperRecord]:
        return self.search(author, window, max_results=max_results)


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value[:10]
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def in_window(value: date, window: DateWindow) -> bool:
    return window.start <= value <= window.end


def first(value):
    if isinstance(value, list):
        return value[0] if value else ""
    return value or ""
