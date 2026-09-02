from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from litreview.dates import initial_last_run_date
from litreview.models import DateWindow, MatchedPaper, SourceDiagnostic


class StateStore:
    def __init__(self, path: Path = Path("state/litreview.sqlite")) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.init()

    def close(self) -> None:
        self.conn.close()

    def init(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                window_start TEXT NOT NULL,
                window_end TEXT NOT NULL,
                status TEXT NOT NULL,
                report_path TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(window_start, window_end)
            );
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                doi TEXT,
                preprint_id TEXT,
                title TEXT NOT NULL,
                payload TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(id)
            );
            CREATE TABLE IF NOT EXISTS diagnostics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                payload TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(id)
            );
            """
        )
        self.conn.commit()

    def get_last_run_date(self, today_now=None) -> date:
        row = self.conn.execute("SELECT value FROM metadata WHERE key = 'last_run_date'").fetchone()
        if row:
            return date.fromisoformat(row["value"])
        value = initial_last_run_date(today_now)
        self.set_last_run_date(value)
        return value

    def set_last_run_date(self, value: date) -> None:
        self.conn.execute(
            """
            INSERT INTO metadata(key, value) VALUES('last_run_date', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (value.isoformat(),),
        )
        self.conn.commit()

    def successful_run_for_window(self, window: DateWindow) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT * FROM runs
            WHERE window_start = ? AND window_end = ? AND status = 'success'
            """,
            (window.start.isoformat(), window.end.isoformat()),
        ).fetchone()

    def save_successful_run(
        self,
        window: DateWindow,
        report_path: Path,
        papers: list[MatchedPaper],
        diagnostics: list[SourceDiagnostic],
        overwrite: bool = False,
    ) -> int:
        existing = self.conn.execute(
            "SELECT id FROM runs WHERE window_start = ? AND window_end = ?",
            (window.start.isoformat(), window.end.isoformat()),
        ).fetchone()
        if existing and overwrite:
            run_id = int(existing["id"])
            self.conn.execute(
                """
                UPDATE runs
                SET status = 'success', report_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (str(report_path), run_id),
            )
            self.conn.execute("DELETE FROM records WHERE run_id = ?", (run_id,))
            self.conn.execute("DELETE FROM diagnostics WHERE run_id = ?", (run_id,))
        else:
            cursor = self.conn.execute(
                """
                INSERT INTO runs(window_start, window_end, status, report_path)
                VALUES(?, ?, 'success', ?)
                """,
                (window.start.isoformat(), window.end.isoformat(), str(report_path)),
            )
            run_id = int(cursor.lastrowid)

        for paper in papers:
            self.conn.execute(
                """
                INSERT INTO records(run_id, source, source_id, doi, preprint_id, title, payload)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    paper.record.source,
                    paper.record.source_id,
                    paper.record.doi,
                    paper.record.preprint_id,
                    paper.record.title,
                    paper.model_dump_json(),
                ),
            )
        for diagnostic in diagnostics:
            self.conn.execute(
                "INSERT INTO diagnostics(run_id, source, payload) VALUES(?, ?, ?)",
                (run_id, diagnostic.source, diagnostic.model_dump_json()),
            )
        self.conn.commit()
        return run_id

    def snapshot(self) -> dict:
        runs = [dict(row) for row in self.conn.execute("SELECT * FROM runs ORDER BY id")]
        metadata = [dict(row) for row in self.conn.execute("SELECT * FROM metadata ORDER BY key")]
        return {"metadata": metadata, "runs": runs}

    def dump_json(self) -> str:
        return json.dumps(self.snapshot(), indent=2)

