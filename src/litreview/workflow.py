from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import httpx

from litreview.classify import classify_record
from litreview.dedupe import dedupe_papers
from litreview.models import DateWindow, MatchedPaper, Registry, SourceDiagnostic
from litreview.render import render_report, write_report
from litreview.sources import (
    ArxivAdapter,
    BiorxivAdapter,
    EuropePmcAdapter,
    MedrxivAdapter,
    OpenAlexAdapter,
)
from litreview.sources.base import SourceAdapter
from litreview.state import StateStore

MAX_DIAGNOSTIC_ERRORS = 12

ADAPTERS: dict[str, type[SourceAdapter]] = {
    "openalex": OpenAlexAdapter,
    "europe_pmc": EuropePmcAdapter,
    "biorxiv": BiorxivAdapter,
    "medrxiv": MedrxivAdapter,
    "arxiv": ArxivAdapter,
}


class RunSkippedError(Exception):
    def __init__(self, message: str, report_path: str = "") -> None:
        self.report_path = report_path
        super().__init__(message)


class SourceRateLimitedError(Exception):
    pass


def run_review(
    registry: Registry,
    window: DateWindow,
    state: StateStore,
    reports_dir: Path = Path("reports"),
    overwrite: bool = False,
    update_last_run: bool = True,
    client: httpx.Client | None = None,
) -> Path:
    existing = state.successful_run_for_window(window)
    report_path = reports_dir / f"{window.end.isoformat()}.md"
    if existing and not overwrite:
        raise RunSkippedError(
            "Report for "
            f"{window.start.isoformat()} to {window.end.isoformat()} "
            "already exists. "
            "Pass --overwrite to regenerate and replace it.",
            existing["report_path"],
        )

    matched, diagnostics = collect_records(registry, window, client=client)
    deduped = dedupe_papers(matched)
    _update_included_counts(diagnostics, deduped)
    content = render_report(registry, window, deduped, diagnostics)
    write_report(report_path, content)
    state.save_successful_run(
        window, report_path, deduped, diagnostics, overwrite=overwrite
    )
    if update_last_run:
        state.set_last_run_date(window.end)
    return report_path


def collect_records(
    registry: Registry,
    window: DateWindow,
    client: httpx.Client | None = None,
) -> tuple[list[MatchedPaper], list[SourceDiagnostic]]:
    matched_by_identity: dict[tuple[str, str], dict[str, object]] = {}
    diagnostics: list[SourceDiagnostic] = []
    enabled_sources = [
        source
        for source in registry.sources
        if source.enabled and source.id in ADAPTERS
    ]

    for source_config in enabled_sources:
        adapter = ADAPTERS[source_config.id](client=client)
        returned_count = 0
        errors: list[str] = []
        retained_by_source = 0
        try:
            for topic in registry.topics:
                if not _topic_uses_source(topic, source_config.id):
                    continue
                query = _topic_query(topic)
                if not query:
                    continue
                try:
                    records = adapter.search(
                        query, window, max_results=source_config.max_results_per_query
                    )
                    returned_count += len(records)
                    for record in records:
                        retained_by_source += 1
                        entry = _entry_for_record(matched_by_identity, record)
                        entry["topics"].add(topic.id)  # type: ignore[union-attr]
                except Exception as exc:
                    _append_error(
                        errors, f"topic {topic.id} / {query}: {_format_exception(exc)}"
                    )
                    if _is_rate_limit(exc):
                        raise SourceRateLimitedError from exc

            for item in registry.watchlist:
                for name in [item.name, *item.aliases]:
                    try:
                        records = adapter.search_author(
                            name,
                            window,
                            max_results=source_config.max_results_per_query,
                            source_id=item.source_ids.get(source_config.id, ""),
                            orcid=item.orcid,
                        )
                        returned_count += len(records)
                        for record in records:
                            retained_by_source += 1
                            entry = _entry_for_record(matched_by_identity, record)
                            entry["watch"].add(item.id)  # type: ignore[union-attr]
                    except Exception as exc:
                        _append_error(
                            errors,
                            f"watch {item.id} / {name}: {_format_exception(exc)}",
                        )
                        if _is_rate_limit(exc):
                            raise SourceRateLimitedError from exc
        except SourceRateLimitedError:
            _append_error(
                errors,
                "Source rate-limited; remaining queries for this source were skipped.",
            )
        finally:
            diagnostics.append(
                SourceDiagnostic(
                    source=source_config.id,
                    request_status="failed" if errors else "ok",
                    retry_count=0,
                    rate_limit_response="",
                    returned_count=returned_count,
                    retained_count=retained_by_source,
                    included_count=0,
                    errors=errors,
                )
            )

    matched: list[MatchedPaper] = []
    for entry in matched_by_identity.values():
        paper = classify_record(
            entry["record"],  # type: ignore[arg-type]
            registry,
            matched_topic_ids=entry["topics"],  # type: ignore[arg-type]
            matched_watch_item_ids=entry["watch"],  # type: ignore[arg-type]
        )
        if paper:
            matched.append(paper)
    return matched, diagnostics


def _entry_for_record(
    store: dict[tuple[str, str], dict[str, object]], record
) -> dict[str, object]:
    key = (record.source, record.source_id or record.title)
    if key not in store:
        store[key] = {"record": record, "topics": set(), "watch": set()}
    return store[key]


def _topic_uses_source(topic, source_id: str) -> bool:
    if topic.sources.include and source_id not in topic.sources.include:
        return False
    return source_id not in topic.sources.exclude


def _topic_query(topic) -> str:
    terms = topic.search_terms or topic.synonyms
    return " ".join(term for term in terms if term.strip())


def _append_error(errors: list[str], error: str) -> None:
    if len(errors) < MAX_DIAGNOSTIC_ERRORS:
        errors.append(error)
    elif len(errors) == MAX_DIAGNOSTIC_ERRORS:
        errors.append("Additional source errors omitted from report.")


def _is_rate_limit(exc: Exception) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429


def _format_exception(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        request = exc.request
        return (
            f"HTTP {exc.response.status_code} {exc.response.reason_phrase} "
            f"for {request.url.host}{request.url.path}"
        )
    return str(exc)


def _update_included_counts(
    diagnostics: list[SourceDiagnostic], papers: list[MatchedPaper]
) -> None:
    counts = defaultdict(int)
    for paper in papers:
        for source in paper.sources:
            counts[source] += 1
    for diagnostic in diagnostics:
        diagnostic.included_count = counts[diagnostic.source]
