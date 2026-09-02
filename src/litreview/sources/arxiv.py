from __future__ import annotations

from datetime import date

import feedparser

from litreview.models import DateWindow, PaperRecord
from litreview.sources.base import SourceAdapter, parse_date


class ArxivAdapter(SourceAdapter):
    source_id = "arxiv"
    api_url = "https://export.arxiv.org/api/query"

    def search(self, query: str, window: DateWindow, max_results: int = 10) -> list[PaperRecord]:
        response = self.client.get(
            self.api_url,
            params={"search_query": f"all:{query}", "start": 0, "max_results": max_results, "sortBy": "submittedDate"},
        )
        response.raise_for_status()
        return [
            record
            for entry in feedparser.parse(response.text).entries
            if (record := self._normalize(entry)) and window.start <= record.publication_or_posting_date <= window.end
        ]

    def search_author(
        self,
        author: str,
        window: DateWindow,
        max_results: int = 10,
        source_id: str = "",
        orcid: str = "",
    ) -> list[PaperRecord]:
        response = self.client.get(
            self.api_url,
            params={"search_query": f'au:"{author}"', "start": 0, "max_results": max_results, "sortBy": "submittedDate"},
        )
        response.raise_for_status()
        return [
            record
            for entry in feedparser.parse(response.text).entries
            if (record := self._normalize(entry)) and window.start <= record.publication_or_posting_date <= window.end
        ]

    def _normalize(self, entry) -> PaperRecord | None:
        posted = parse_date(getattr(entry, "published", "") or getattr(entry, "updated", ""))
        if posted is None:
            return None
        arxiv_id = getattr(entry, "id", "")
        authors = [author.get("name", "") for author in getattr(entry, "authors", [])]
        return PaperRecord(
            source=self.source_id,
            source_id=arxiv_id,
            doi=getattr(entry, "arxiv_doi", ""),
            title=" ".join(getattr(entry, "title", "").split()),
            authors=[author for author in authors if author],
            author_identifiers={},
            publication_or_posting_date=posted,
            year=posted.year,
            venue="arXiv",
            abstract=" ".join(getattr(entry, "summary", "").split()),
            url=arxiv_id,
            raw_type="preprint",
            preprint_id=arxiv_id.rsplit("/", 1)[-1],
        )
