from __future__ import annotations

from datetime import date
from pathlib import Path

from litreview.models import DateWindow, PaperRecord
from litreview.registry import load_registry
from litreview.sources.base import SourceAdapter
from litreview.workflow import ADAPTERS, collect_records


class FakeAuthorAdapter(SourceAdapter):
    source_id = "openalex"
    api_url = "https://example.test"
    topic_queries = 0
    author_queries = 0

    def search(
        self, query: str, window: DateWindow, max_results: int = 10
    ) -> list[PaperRecord]:
        self.__class__.topic_queries += 1
        raise AssertionError("topic search should not run")

    def search_author(
        self,
        author: str,
        window: DateWindow,
        max_results: int = 10,
        source_id: str = "",
        orcid: str = "",
    ) -> list[PaperRecord]:
        self.__class__.author_queries += 1
        return [
            PaperRecord(
                source=self.source_id,
                source_id=author,
                title=f"{author} paper",
                authors=[author],
                publication_or_posting_date=window.end,
                year=window.end.year,
                venue="Journal",
            )
        ]


def test_author_only_skips_topic_searches(monkeypatch) -> None:
    registry = load_registry(Path("registry.example.yaml"))
    registry.sources = [source for source in registry.sources if source.id == "openalex"]
    FakeAuthorAdapter.topic_queries = 0
    FakeAuthorAdapter.author_queries = 0
    monkeypatch.setitem(ADAPTERS, "openalex", FakeAuthorAdapter)

    matched, diagnostics = collect_records(
        registry,
        DateWindow(start=date(2026, 8, 24), end=date(2026, 8, 31)),
        author_only=True,
    )

    assert FakeAuthorAdapter.topic_queries == 0
    assert FakeAuthorAdapter.author_queries > 0
    assert matched
    assert {paper.match.relevance_label for paper in matched} == {"medium"}
    assert diagnostics[0].request_status == "ok"
