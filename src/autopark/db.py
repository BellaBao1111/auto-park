import sqlite3
from contextlib import closing
from dataclasses import dataclass, fields
from datetime import datetime

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone TEXT NOT NULL,
    space TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    run_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result_message TEXT,
    created_at TEXT NOT NULL
);
"""


@dataclass
class Job:
    id: int
    zone: str
    space: str
    duration_minutes: int
    run_at: str
    status: str
    result_message: str | None
    created_at: str


# Column list shared by every SELECT, kept in the dataclass field order so
# `_row_to_job` can map positionally without drifting out of sync.
_COLUMNS = ", ".join(f.name for f in fields(Job))


def _connect() -> sqlite3.Connection:
    # Read config.DB_PATH at call time (not import time) so tests can point it
    # at a temporary database.
    return sqlite3.connect(config.DB_PATH)


def _row_to_job(row) -> Job:
    return Job(*row)


def init_db():
    with closing(_connect()) as conn:
        conn.execute(SCHEMA)
        conn.commit()


def add_job(zone: str, space: str, duration_minutes: int, run_at: datetime) -> int:
    with closing(_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO jobs (zone, space, duration_minutes, run_at, status, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?)",
            (zone, space, duration_minutes, run_at.isoformat(), datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid


def get_pending_due(now: datetime) -> list[Job]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM jobs WHERE status = 'pending' AND run_at <= ?",
            (now.isoformat(),),
        ).fetchall()
        return [_row_to_job(r) for r in rows]


def get_latest_pending() -> Job | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM jobs WHERE status = 'pending' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return _row_to_job(row) if row else None


def mark_job(job_id: int, status: str, result_message: str | None = None):
    with closing(_connect()) as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, result_message = ? WHERE id = ?",
            (status, result_message, job_id),
        )
        conn.commit()


def cancel_latest_pending() -> Job | None:
    job = get_latest_pending()
    if job:
        mark_job(job.id, "cancelled")
    return job
