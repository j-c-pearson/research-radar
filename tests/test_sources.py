from __future__ import annotations

from datetime import date

import httpx

from litreview.models import DateWindow
from litreview.sources import ArxivAdapter, BiorxivAdapter, EuropePmcAdapter, OpenAlexAdapter


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openalex_normalization() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "https://openalex.org/W1",
                        "doi": "https://doi.org/10.1/ABC",
                        "title": "A paper",
                        "publication_date": "2026-08-30",
                        "publication_year": 2026,
                        "authorships": [{"author": {"display_name": "A Author", "id": "A1"}}],
                        "primary_location": {"source": {"display_name": "Venue"}},
                        "abstract_inverted_index": {"hello": [0], "world": [1]},
                        "type": "article",
                    }
                ]
            },
        )

    records = OpenAlexAdapter(client_for(handler)).search("paper", DateWindow(start=date(2026, 8, 24), end=date(2026, 8, 31)))

    assert records[0].doi == "10.1/abc"
    assert records[0].abstract == "hello world"
    assert records[0].authors == ["A Author"]


def test_openalex_author_search_uses_raw_author_name_filter() -> None:
    seen_filter = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_filter
        seen_filter = request.url.params["filter"]
        return httpx.Response(200, json={"results": []})

    OpenAlexAdapter(client_for(handler)).search_author(
        "Sigurd Skogestad",
        DateWindow(start=date(2026, 8, 24), end=date(2026, 8, 31)),
    )

    assert 'raw_author_name.search:"Sigurd Skogestad"' in seen_filter
    assert "authorships.author.search" not in seen_filter


def test_openalex_author_search_prefers_orcid_and_source_id() -> None:
    seen_filters: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_filters.append(request.url.params["filter"])
        return httpx.Response(200, json={"results": []})

    adapter = OpenAlexAdapter(client_for(handler))
    window = DateWindow(start=date(2026, 8, 24), end=date(2026, 8, 31))
    adapter.search_author("Cristina Stoica", window, orcid="0000-0002-5838-599X")
    adapter.search_author("Known Author", window, source_id="https://openalex.org/A123")

    assert "authorships.author.orcid:0000-0002-5838-599X" in seen_filters[0]
    assert "authorships.author.id:A123" in seen_filters[1]


def test_europepmc_normalization() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "resultList": {
                    "result": [
                        {
                            "id": "1",
                            "doi": "10.2/example",
                            "title": "Bio paper",
                            "firstPublicationDate": "2026-08-29",
                            "pubYear": "2026",
                            "journalTitle": "Journal",
                            "authorList": {"author": [{"fullName": "Bio Author"}]},
                            "abstractText": "Abstract",
                            "pubType": "research article",
                        }
                    ]
                }
            },
        )

    records = EuropePmcAdapter(client_for(handler)).search("bio", DateWindow(start=date(2026, 8, 24), end=date(2026, 8, 31)))

    assert records[0].source == "europe_pmc"
    assert records[0].title == "Bio paper"


def test_biorxiv_normalization() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "collection": [
                    {
                        "doi": "10.1101/test",
                        "title": "Synthetic biology preprint",
                        "authors": "A Author; B Author",
                        "date": "2026-08-28",
                        "abstract": "Synthetic biology abstract",
                    }
                ]
            },
        )

    records = BiorxivAdapter(client_for(handler)).search("synthetic biology", DateWindow(start=date(2026, 8, 24), end=date(2026, 8, 31)))

    assert records[0].preprint_id == "10.1101/test"
    assert records[0].authors == ["A Author", "B Author"]


def test_arxiv_normalization() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2608.12345v1</id>
        <title>State estimation paper</title>
        <summary>Abstract text</summary>
        <published>2026-08-27T00:00:00Z</published>
        <author><name>A Author</name></author>
      </entry>
    </feed>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=xml)

    records = ArxivAdapter(client_for(handler)).search("state estimation", DateWindow(start=date(2026, 8, 24), end=date(2026, 8, 31)))

    assert records[0].source == "arxiv"
    assert records[0].preprint_id == "2608.12345v1"
