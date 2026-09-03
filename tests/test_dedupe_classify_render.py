from __future__ import annotations

from datetime import date
from pathlib import Path

from litreview.classify import classify_record
from litreview.dedupe import clean_title, dedupe_papers
from litreview.models import DateWindow, PaperRecord, SourceDiagnostic
from litreview.registry import load_registry
from litreview.render import render_report


def record(title: str, doi: str = "", preprint_id: str = "", authors: list[str] | None = None) -> PaperRecord:
    return PaperRecord(
        source="openalex",
        source_id=title,
        doi=doi,
        title=title,
        authors=authors or [],
        publication_or_posting_date=date(2026, 8, 31),
        year=2026,
        venue="Journal",
        volume="12",
        issue="3",
        abstract="This paper studies synthetic biology and state estimation.",
        preprint_id=preprint_id,
    )


def test_clean_title_exact_policy() -> None:
    assert clean_title("  A Title:  ") == "a title"
    assert clean_title("A   Title") == "a title"
    assert clean_title("A related title") != clean_title("A related titles")


def test_dedupe_by_doi_preprint_and_cleaned_title() -> None:
    registry = load_registry(Path("registry.example.yaml"))
    p1 = classify_record(record("Title A", doi="10.1234/X"), registry, {"self_supervised_learning"}, set())
    p2 = classify_record(record("Title B", doi="https://doi.org/10.1234/x"), registry, {"self_supervised_learning"}, set())
    p3 = classify_record(record("Different", preprint_id="abc"), registry, {"self_supervised_learning"}, set())
    p4 = classify_record(record("Another", preprint_id="ABC"), registry, {"self_supervised_learning"}, set())
    p5 = classify_record(record("Same Title."), registry, {"self_supervised_learning"}, set())
    p6 = classify_record(record("same   title"), registry, {"self_supervised_learning"}, set())

    deduped = dedupe_papers([p for p in [p1, p2, p3, p4, p5, p6] if p])

    assert len(deduped) == 3


def test_relevance_labels() -> None:
    registry = load_registry(Path("registry.example.yaml"))

    low = classify_record(record("Topic"), registry, {"self_supervised_learning"}, set())
    medium = classify_record(record("Author", authors=["Example Author"]), registry, set(), {"example_author"})
    high = classify_record(record("Both", authors=["Example Author"]), registry, {"self_supervised_learning"}, {"example_author"})

    assert low and low.match.relevance_label == "low"
    assert medium and medium.match.relevance_label == "medium"
    assert high and high.match.relevance_label == "high"


def test_report_doi_abstract_and_no_summary() -> None:
    registry = load_registry(Path("registry.example.yaml"))
    paper = classify_record(
        record("Report Item", doi="10.1234/example", authors=["Ada Lovelace", "Grace Hopper"]),
        registry,
        {"self_supervised_learning"},
        set(),
    )
    assert paper
    content = render_report(
        registry,
        DateWindow(start=date(2026, 8, 24), end=date(2026, 8, 31)),
        [paper],
        [SourceDiagnostic(source="openalex", request_status="ok")],
    )

    assert "## Low relevance" in content
    assert "### Machine learning" in content
    assert "[10.1234/example](https://doi.org/10.1234/example)" in content
    assert "- Authors: Ada Lovelace, Grace Hopper" in content
    assert "- Published/available online: 2026-08-31" in content
    assert "```bibtex\n@article{lovelace2026report," in content
    assert "  author = {Ada Lovelace and Grace Hopper}" in content
    assert "  journal = {Journal}" in content
    assert "  volume = {12}" in content
    assert "  number = {3}" in content
    assert "- Abstract:" in content
    assert "summary" not in content.lower()


def test_report_omits_missing_abstract() -> None:
    registry = load_registry(Path("registry.example.yaml"))
    paper = classify_record(record("No Abstract"), registry, {"self_supervised_learning"}, set())
    assert paper
    paper.record.abstract = ""

    content = render_report(
        registry,
        DateWindow(start=date(2026, 8, 24), end=date(2026, 8, 31)),
        [paper],
        [],
    )

    assert "- Abstract:" not in content


def test_report_groups_by_relevance_then_category() -> None:
    registry = load_registry(Path("registry.example.yaml"))
    low = classify_record(record("Low"), registry, {"self_supervised_learning"}, set())
    high = classify_record(record("High", authors=["Example Author"]), registry, {"self_supervised_learning"}, {"example_author"})
    medium = classify_record(record("Medium", authors=["Example Author"]), registry, set(), {"example_author"})
    assert low and medium and high

    content = render_report(
        registry,
        DateWindow(start=date(2026, 8, 24), end=date(2026, 8, 31)),
        [low, medium, high],
        [],
    )

    assert content.index("## High relevance") < content.index("## Medium relevance")
    assert content.index("## Medium relevance") < content.index("## Low relevance")
    assert "### Watched authors / no topic" in content
