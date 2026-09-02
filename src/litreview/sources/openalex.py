from __future__ import annotations

from typing import Any

from litreview.models import DateWindow, PaperRecord
from litreview.sources.base import SourceAdapter, parse_date


class OpenAlexAdapter(SourceAdapter):
    source_id = "openalex"
    api_url = "https://api.openalex.org/works"

    def search(
        self, query: str, window: DateWindow, max_results: int = 10
    ) -> list[PaperRecord]:
        response = self.client.get(
            self.api_url,
            params={
                "search": query,
                "filter": _date_filter(window),
                "per-page": max_results,
            },
        )
        response.raise_for_status()
        return [
            record
            for item in response.json().get("results", [])
            if (record := self._normalize(item))
        ]

    def search_author(
        self,
        author: str,
        window: DateWindow,
        max_results: int = 10,
        source_id: str = "",
        orcid: str = "",
    ) -> list[PaperRecord]:
        author_filter = _author_filter(author=author, source_id=source_id, orcid=orcid)
        response = self.client.get(
            self.api_url,
            params={
                "filter": f"{author_filter},{_date_filter(window)}",
                "per-page": max_results,
            },
        )
        response.raise_for_status()
        return [
            record
            for item in response.json().get("results", [])
            if (record := self._normalize(item))
        ]

    def _normalize(self, item: dict[str, Any]) -> PaperRecord | None:
        publication_date = parse_date(item.get("publication_date"))
        if publication_date is None:
            return None
        title = item.get("title") or item.get("display_name") or ""
        if not title:
            return None
        authorships = item.get("authorships") or []
        authors = [
            author.get("display_name", "")
            for authorship in authorships
            if (author := authorship.get("author") or {})
        ]
        author_ids = {
            "openalex": [
                author.get("id", "")
                for authorship in authorships
                if (author := authorship.get("author") or {}) and author.get("id")
            ]
        }
        venue = (
            ((item.get("primary_location") or {}).get("source") or {}).get(
                "display_name"
            )
            or (item.get("host_venue") or {}).get("display_name")
            or ""
        )
        doi = item.get("doi") or ""
        abstract = _openalex_abstract(item.get("abstract_inverted_index") or {})
        return PaperRecord(
            source=self.source_id,
            source_id=item.get("id", ""),
            doi=doi,
            title=title,
            authors=authors,
            author_identifiers=author_ids,
            publication_or_posting_date=publication_date,
            year=item.get("publication_year") or publication_date.year,
            venue=venue,
            volume=str((item.get("biblio") or {}).get("volume") or ""),
            issue=str((item.get("biblio") or {}).get("issue") or ""),
            abstract=abstract,
            url=item.get("id", ""),
            raw_type=item.get("type") or "",
            raw=item,
        )


def _openalex_abstract(index: dict[str, list[int]]) -> str:
    if not index:
        return ""
    words = sorted(
        (
            (position, word)
            for word, positions in index.items()
            for position in positions
        )
    )
    return " ".join(word for _, word in words)


def _author_filter(author: str, source_id: str = "", orcid: str = "") -> str:
    if source_id:
        return f"authorships.author.id:{_normalize_openalex_author_id(source_id)}"
    if orcid:
        return f"authorships.author.orcid:{orcid.removeprefix('https://orcid.org/')}"
    return f'raw_author_name.search:"{author}"'


def _date_filter(window: DateWindow) -> str:
    return (
        f"from_publication_date:{window.start.isoformat()},"
        f"to_publication_date:{window.end.isoformat()}"
    )


def _normalize_openalex_author_id(source_id: str) -> str:
    return source_id.strip().removeprefix("https://openalex.org/")
