from __future__ import annotations

from typing import Any

from litreview.models import DateWindow, PaperRecord
from litreview.sources.base import SourceAdapter, first, parse_date


class EuropePmcAdapter(SourceAdapter):
    source_id = "europe_pmc"
    api_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def search(
        self, query: str, window: DateWindow, max_results: int = 10
    ) -> list[PaperRecord]:
        date_clause = (
            f"FIRST_PDATE:[{window.start.isoformat()} TO {window.end.isoformat()}]"
        )
        response = self.client.get(
            self.api_url,
            params={
                "query": f"({query}) AND {date_clause}",
                "format": "json",
                "pageSize": max_results,
            },
        )
        response.raise_for_status()
        results = response.json().get("resultList", {}).get("result", [])
        return [record for item in results if (record := self._normalize(item))]

    def search_author(
        self,
        author: str,
        window: DateWindow,
        max_results: int = 10,
        source_id: str = "",
        orcid: str = "",
    ) -> list[PaperRecord]:
        date_clause = (
            f"FIRST_PDATE:[{window.start.isoformat()} TO {window.end.isoformat()}]"
        )
        response = self.client.get(
            self.api_url,
            params={
                "query": f'AUTH:"{author}" AND {date_clause}',
                "format": "json",
                "pageSize": max_results,
            },
        )
        response.raise_for_status()
        results = response.json().get("resultList", {}).get("result", [])
        return [record for item in results if (record := self._normalize(item))]

    def _normalize(self, item: dict[str, Any]) -> PaperRecord | None:
        publication_date = parse_date(
            item.get("firstPublicationDate") or item.get("firstIndexDate")
        )
        if publication_date is None:
            return None
        title = item.get("title") or ""
        if not title:
            return None
        authors = [
            author.get("fullName", "")
            for author in item.get("authorList", {}).get("author", [])
        ]
        return PaperRecord(
            source=self.source_id,
            source_id=item.get("id") or item.get("pmid") or item.get("pmcid") or "",
            doi=item.get("doi") or "",
            title=title,
            authors=[author for author in authors if author],
            author_identifiers={},
            publication_or_posting_date=publication_date,
            year=int(item["pubYear"])
            if str(item.get("pubYear", "")).isdigit()
            else publication_date.year,
            venue=first(item.get("journalTitle")),
            volume=str(item.get("journalVolume") or ""),
            issue=str(item.get("issue") or ""),
            abstract=item.get("abstractText") or "",
            url=item.get("fullTextUrlList", {})
            .get("fullTextUrl", [{}])[0]
            .get("url", "")
            if item.get("fullTextUrlList")
            else "",
            raw_type=item.get("pubType") or "",
            raw=item,
        )
