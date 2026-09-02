from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from litreview.models import DateWindow, MatchedPaper, Registry, SourceDiagnostic

RELEVANCE_ORDER = ["high", "medium", "low"]
RELEVANCE_HEADINGS = {
    "high": "High relevance",
    "medium": "Medium relevance",
    "low": "Low relevance",
}


def render_report(
    registry: Registry,
    window: DateWindow,
    papers: list[MatchedPaper],
    diagnostics: list[SourceDiagnostic],
) -> str:
    category_names = {category.id: category.name for category in registry.categories}
    subcategory_names = {
        (category.id, subcategory.id): subcategory.name
        for category in registry.categories
        for subcategory in category.subcategories
    }
    grouped: dict[tuple[str, str, str], list[MatchedPaper]] = defaultdict(list)
    for paper in papers:
        relevance = (
            paper.match.relevance_label.value if paper.match.relevance_label else "low"
        )
        grouped[(relevance, paper.match.category, paper.match.subcategory)].append(
            paper
        )

    lines = [
        (
            "# Weekly Literature Report: "
            f"{window.start.isoformat()} to {window.end.isoformat()}"
        ),
        "",
        f"Included items: {len(papers)}",
        "",
    ]

    for relevance in RELEVANCE_ORDER:
        relevance_groups = {
            (category_id, subcategory_id): items
            for (label, category_id, subcategory_id), items in grouped.items()
            if label == relevance
        }
        if not relevance_groups:
            continue
        lines.extend([f"## {RELEVANCE_HEADINGS[relevance]}", ""])
        for (category_id, subcategory_id), items in sorted(relevance_groups.items()):
            category = category_names.get(
                category_id, category_id or "Watched authors / no topic"
            )
            subcategory = subcategory_names.get(
                (category_id, subcategory_id), subcategory_id or "Unclassified"
            )
            lines.extend([f"### {category}", "", f"#### {subcategory}", ""])
            for paper in sorted(
                items,
                key=lambda item: item.record.publication_or_posting_date,
                reverse=True,
            ):
                lines.extend(_render_item(paper))

    watched = [paper for paper in papers if paper.match.matched_watch_item_ids]
    if watched:
        lines.extend(["## Watched Authors/PIs", ""])
        watch_names = {item.id: item.name for item in registry.watchlist}
        for paper in watched:
            names = [
                watch_names.get(item_id, item_id)
                for item_id in paper.match.matched_watch_item_ids
            ]
            lines.append(f"- {paper.record.title} ({', '.join(names)})")
        lines.append("")

    lines.extend(["## Source Diagnostics", ""])
    for diagnostic in diagnostics:
        lines.extend(
            [
                f"### {diagnostic.source}",
                "",
                f"- Request status: {diagnostic.request_status}",
                f"- Retry count: {diagnostic.retry_count}",
                f"- Rate-limit response: {diagnostic.rate_limit_response}",
                f"- Records returned: {diagnostic.returned_count}",
                f"- Records retained after date filtering: {diagnostic.retained_count}",
                (
                    "- Records included after relevance labeling: "
                    f"{diagnostic.included_count}"
                ),
            ]
        )
        if diagnostic.errors:
            lines.append(f"- Errors: {'; '.join(diagnostic.errors)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content)
    tmp_path.replace(path)


def _render_item(paper: MatchedPaper) -> list[str]:
    record = paper.record
    citation = _bibtex(record)
    doi = f"[{record.doi}](https://doi.org/{record.doi})" if record.doi else ""
    lines = [
        f"##### {record.title}",
        "",
        f"- Authors: {_authors(record)}",
        (
            "- Published/available online: "
            f"{record.publication_or_posting_date.isoformat()}"
        ),
        f"- Source: {', '.join(paper.sources or [record.source])}",
    ]
    if doi:
        lines.append(f"- DOI: {doi}")
    lines.extend(
        [
            f"- Title: {record.title}",
        ]
    )
    if record.abstract:
        lines.append(f"- Abstract: {record.abstract}")
    lines.extend(
        [
            (
                "- Category and subcategory: "
                f"{paper.match.category} / {paper.match.subcategory}"
            ),
            f"- Relevance label: {_relevance_label(paper)}",
            "- Citation metadata:",
            "",
            "```bibtex",
            citation,
            "```",
            "",
        ]
    )
    return lines


def _authors(record) -> str:
    return ", ".join(record.authors) if record.authors else "Unknown authors"


def _relevance_label(paper: MatchedPaper) -> str:
    return paper.match.relevance_label.value if paper.match.relevance_label else ""


def _bibtex(record) -> str:
    entry_type = (
        "misc"
        if record.raw_type == "preprint"
        or record.venue.lower() in {"arxiv", "biorxiv", "medrxiv"}
        else "article"
    )
    fields = [
        ("title", record.title),
        ("author", " and ".join(record.authors)),
        ("year", str(record.year or record.publication_or_posting_date.year)),
        ("journal", record.venue),
        ("volume", record.volume),
        ("number", record.issue),
        ("doi", record.doi),
        ("url", record.url),
    ]
    rendered_fields = [
        f"  {name} = {{{_escape_bibtex(value)}}}" for name, value in fields if value
    ]
    return (
        f"@{entry_type}{{{_bibtex_key(record)},\n" + ",\n".join(rendered_fields) + "\n}"
    )


def _bibtex_key(record) -> str:
    first_author = record.authors[0] if record.authors else "unknown"
    surname = (
        re.sub(r"[^A-Za-z0-9]+", "", first_author.split()[-1]).lower() or "unknown"
    )
    title_word = next(
        (
            re.sub(r"[^A-Za-z0-9]+", "", word).lower()
            for word in record.title.split()
            if word
        ),
        "paper",
    )
    return (
        f"{surname}{record.year or record.publication_or_posting_date.year}{title_word}"
    )


def _escape_bibtex(value: str) -> str:
    return (
        value.replace("\\", "\\textbackslash{}").replace("{", "\\{").replace("}", "\\}")
    )
