import pytest

from autopark import config, db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the db module at a throwaway SQLite file and initialize it."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "jobs.db")
    db.init_db()
    return config.DB_PATH
