from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Priority(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class RelevanceLabel(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class Subcategory(BaseModel):
    id: str
    name: str
    notes: str = ""


class Category(BaseModel):
    id: str
    name: str
    notes: str = ""
    subcategories: list[Subcategory] = Field(default_factory=list)


class TopicSources(BaseModel):
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class Topic(BaseModel):
    id: str
    name: str
    category: str
    subcategory: str
    priority: Priority
    search_terms: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    include_when: list[str] = Field(default_factory=list)
    exclude_when: list[str] = Field(default_factory=list)
    notes: str = ""
    sources: TopicSources = Field(default_factory=TopicSources)

    @property
    def query_terms(self) -> list[str]:
        return [term for term in [*self.search_terms, *self.synonyms] if term.strip()]


class WatchItem(BaseModel):
    id: str
    name: str
    type: str = "author"
    affiliation: str = ""
    orcid: str = ""
    profile_urls: list[str] = Field(default_factory=list)
    source_ids: dict[str, str] = Field(default_factory=dict)
    related_topics: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    priority: Priority = Priority.medium
    notes: str = ""

    @field_validator("orcid")
    @classmethod
    def normalize_orcid(cls, value: str) -> str:
        value = value.strip()
        prefix = "https://orcid.org/"
        if value.startswith(prefix):
            return value.removeprefix(prefix)
        return value


class SourceConfig(BaseModel):
    id: str
    name: str
    enabled: bool = True
    api_url: str
    priority: Priority = Priority.medium
    date_field_policy: str = ""
    max_results_per_query: int = 10
    notes: str = ""


class RegistryMetadata(BaseModel):
    name: str
    description: str = ""


class RelevanceRules(BaseModel):
    labels: dict[str, str]


class ChangeLogEntry(BaseModel):
    date: str = ""
    change: str = ""
    reason: str = ""


class Registry(BaseModel):
    version: int
    metadata: RegistryMetadata
    categories: list[Category]
    topics: list[Topic]
    watchlist: list[WatchItem]
    sources: list[SourceConfig]
    relevance_rules: RelevanceRules
    change_log: list[ChangeLogEntry] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class PaperRecord(BaseModel):
    source: str
    source_id: str
    doi: str = ""
    title: str
    authors: list[str] = Field(default_factory=list)
    author_identifiers: dict[str, list[str]] = Field(default_factory=dict)
    publication_or_posting_date: date
    year: int | None = None
    venue: str = ""
    volume: str = ""
    issue: str = ""
    abstract: str = ""
    url: str = ""
    raw_type: str = ""
    preprint_id: str = ""
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @field_validator("doi")
    @classmethod
    def normalize_doi(cls, value: str) -> str:
        value = value.strip()
        value = value.removeprefix("https://doi.org/")
        value = value.removeprefix("http://doi.org/")
        return value.lower()


class MatchInfo(BaseModel):
    matched_topic_ids: list[str] = Field(default_factory=list)
    matched_watch_item_ids: list[str] = Field(default_factory=list)
    category: str = ""
    subcategory: str = ""
    relevance_label: RelevanceLabel | None = None


class MatchedPaper(BaseModel):
    record: PaperRecord
    match: MatchInfo
    sources: list[str] = Field(default_factory=list)
    duplicate_record_ids: list[str] = Field(default_factory=list)


class SourceDiagnostic(BaseModel):
    source: str
    request_status: str
    retry_count: int = 0
    rate_limit_response: str = ""
    returned_count: int = 0
    retained_count: int = 0
    included_count: int = 0
    errors: list[str] = Field(default_factory=list)


class DateWindow(BaseModel):
    start: date
    end: date
