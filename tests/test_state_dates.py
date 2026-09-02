from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from litreview.models import DateWindow
from litreview.registry import load_registry
from litreview.state import StateStore
from litreview.workflow import RunSkipped, run_review


def test_initial_last_run_is_seven_days_before(tmp_path: Path) -> None:
    state = StateStore(tmp_path / "state.sqlite")
    try:
        assert state.get_last_run_date(datetime(2026, 8, 31)) == date(2026, 8, 24)
    finally:
        state.close()


def test_duplicate_window_skip_and_overwrite(tmp_path: Path) -> None:
    registry = load_registry(Path("registry.yaml"))
    for source in registry.sources:
        source.enabled = False
    state = StateStore(tmp_path / "state.sqlite")
    reports = tmp_path / "reports"
    window = DateWindow(start=date(2026, 8, 24), end=date(2026, 8, 31))

    try:
        path = run_review(registry, window, state, reports_dir=reports, client=None, update_last_run=False)
        original = path.read_text()

        with pytest.raises(RunSkipped):
            run_review(registry, window, state, reports_dir=reports, client=None, update_last_run=False)

        path.write_text("old")
        replacement = run_review(
            registry,
            window,
            state,
            reports_dir=reports,
            overwrite=True,
            client=None,
            update_last_run=False,
        )
        assert replacement == path
        assert path.read_text() != "old"
        assert path.read_text() == original
    finally:
        state.close()
