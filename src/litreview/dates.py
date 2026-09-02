from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from litreview.models import DateWindow

LONDON_TZ = ZoneInfo("Europe/London")


def london_today(now: datetime | None = None) -> date:
    if now is None:
        now = datetime.now(tz=LONDON_TZ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=LONDON_TZ)
    return now.astimezone(LONDON_TZ).date()


def initial_last_run_date(now: datetime | None = None) -> date:
    return london_today(now) - timedelta(days=7)


def default_window(last_run: date, now: datetime | None = None) -> DateWindow:
    return DateWindow(start=last_run, end=london_today(now))


def parse_date(value: str) -> date:
    return date.fromisoformat(value)

