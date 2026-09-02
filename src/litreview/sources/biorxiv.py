from __future__ import annotations

from typing import Any

from litreview.models import DateWindow, PaperRecord
from litreview.sources.base import SourceAdapter, parse_date


class _RxivAdapter(SourceAdapter):
    server = "biorxiv"
    source_id = "biorxiv"
    _window_cache: dict[tuple[str, str], list[PaperRecord]]

    def __init__(self, client=None) -> None:
        super().__init__(client=client)
        self._window_cache = {}

    @property
    def api_url(self) -> str:  # type: ignore[override]
        return f"https://api.biorxiv.org/details/{self.server}"

    def search(self, query: str, window: DateWindow, max_results: int = 10) -> list[PaperRecord]:
        records = self._date_window_records(window)
        return [record for record in records if query.lower() in f"{record.title} {record.abstract}".lower()][:max_results]

    def search_author(
        self,
        author: str,
        window: DateWindow,
        max_results: int = 10,
        source_id: str = "",
        orcid: str = "",
    ) -> list[PaperRecord]:
        records = self._date_window_records(window)
        return [record for record in records if author.lower() in " ".join(record.authors).lower()][:max_results]

    def _date_window_records(self, window: DateWindow) -> list[PaperRecord]:
        key = (window.start.isoformat(), window.end.isoformat())
        if key in self._window_cache:
            return self._window_cache[key]
        response = self.client.get(f"{self.api_url}/{window.start.isoformat()}/{window.end.isoformat()}")
        response.raise_for_status()
        records = [record for item in response.json().get("collection", []) if (record := self._normalize(item))]
        self._window_cache[key] = records
        return records

    def _normalize(self, item: dict[str, Any]) -> PaperRecord | None:
        posted = parse_date(item.get("date"))
        if posted is None:
            return None
        title = item.get("title") or ""
        if not title:
            return None
        doi = item.get("doi") or ""
        return PaperRecord(
            source=self.source_id,
            source_id=doi or title,
            doi=doi,
            title=title,
            authors=_split_authors(item.get("authors") or ""),
            author_identifiers={},
            publication_or_posting_date=posted,
            year=posted.year,
            venue=self.server,
            abstract=item.get("abstract") or "",
            url=item.get("url") or (f"https://doi.org/{doi}" if doi else ""),
            raw_type="preprint",
            preprint_id=doi,
            raw=item,
        )


class BiorxivAdapter(_RxivAdapter):
    server = "biorxiv"
    source_id = "biorxiv"


class MedrxivAdapter(_RxivAdapter):
    server = "medrxiv"
    source_id = "medrxiv"


def _split_authors(value: str) -> list[str]:
    return [author.strip() for author in value.replace(";", ",").split(",") if author.strip()]
