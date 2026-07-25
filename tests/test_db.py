from datetime import datetime, timedelta

from autopark import db


def test_add_and_get_latest_pending(temp_db):
    run_at = datetime(2026, 7, 25, 9, 5)
    job_id = db.add_job("408", "503", 60, run_at)

    job = db.get_latest_pending()
    assert job is not None
    assert job.id == job_id
    assert job.zone == "408"
    assert job.space == "503"
    assert job.duration_minutes == 60
    assert job.status == "pending"
    assert job.run_at == run_at.isoformat()


def test_get_latest_pending_returns_newest(temp_db):
    db.add_job("1", "1", 15, datetime(2026, 7, 25, 9, 0))
    second = db.add_job("2", "2", 30, datetime(2026, 7, 25, 10, 0))

    job = db.get_latest_pending()
    assert job.id == second
    assert job.zone == "2"


def test_get_pending_due_only_returns_due_jobs(temp_db):
    now = datetime(2026, 7, 25, 9, 5)
    due_id = db.add_job("1", "1", 15, now - timedelta(minutes=1))
    db.add_job("2", "2", 15, now + timedelta(hours=1))  # not yet due

    due = db.get_pending_due(now)
    assert [j.id for j in due] == [due_id]


def test_mark_job_updates_status_and_message(temp_db):
    job_id = db.add_job("1", "1", 15, datetime(2026, 7, 25, 9, 0))
    db.mark_job(job_id, "done", "Payment submitted.")

    # A completed job is no longer pending.
    assert db.get_latest_pending() is None


def test_marked_job_is_excluded_from_pending_due(temp_db):
    now = datetime(2026, 7, 25, 9, 5)
    job_id = db.add_job("1", "1", 15, now - timedelta(minutes=1))
    db.mark_job(job_id, "running")

    assert db.get_pending_due(now) == []


def test_cancel_latest_pending(temp_db):
    job_id = db.add_job("1", "1", 15, datetime(2026, 7, 25, 9, 0))

    cancelled = db.cancel_latest_pending()
    assert cancelled.id == job_id
    assert db.get_latest_pending() is None


def test_cancel_latest_pending_when_empty(temp_db):
    assert db.cancel_latest_pending() is None
