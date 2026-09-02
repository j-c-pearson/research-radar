from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from os import environ

import httpx

from litreview.models import DateWindow, PaperRecord, SourceAuthConfig, SourceConfig


@dataclass
class RetrievedPaper:
    record: PaperRecord
    matched_topic_ids: set[str] = field(default_factory=set)
    matched_watch_item_ids: set[str] = field(default_factory=set)


class SourceAdapter:
    source_id: str
    api_url: str

    def __init__(
        self,
        client: httpx.Client | None = None,
        source_config: SourceConfig | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.client = client or httpx.Client(timeout=10.0, follow_redirects=True)
        self.source_config = source_config
        self.env = env if env is not None else environ
        self.auth_mode = "unauthenticated"

    def search(
        self, query: str, window: DateWindow, max_results: int = 10
    ) -> list[PaperRecord]:
        raise NotImplementedError

    def search_author(
        self,
        author: str,
        window: DateWindow,
        max_results: int = 10,
        source_id: str = "",
        orcid: str = "",
    ) -> list[PaperRecord]:
        return self.search(author, window, max_results=max_results)

    @property
    def auth(self) -> SourceAuthConfig:
        if self.source_config is not None:
            return self.source_config.auth
        return SourceAuthConfig()

    def api_key(self) -> str:
        key_env = self.auth.api_key_env
        return self.env.get(key_env, "").strip() if key_env else ""

    def auth_query_params(self) -> dict[str, str]:
        auth = self.auth
        key = self.api_key()
        if auth.mode == "optional" and auth.placement == "query" and key:
            self.auth_mode = "authenticated"
            return {auth.parameter: key}
        self.auth_mode = "unauthenticated"
        return {}


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value[:10]
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def in_window(value: date, window: DateWindow) -> bool:
    return window.start <= value <= window.end


def first(value):
    if isinstance(value, list):
        return value[0] if value else ""
    return value or ""
