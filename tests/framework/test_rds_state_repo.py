import asyncio
from datetime import date

from framework.persistence.sqlite import SQLiteRDSStateRepository


def _run(coro):
    return asyncio.run(coro)


def test_save_then_load_roundtrips_dates_as_date_objects(tmp_path):
    repo = SQLiteRDSStateRepository(str(tmp_path / "t.db"))
    temps = [
        {"date": date(2026, 7, 1), "temp": 31.0, "humidity": 70.0},
        {"date": date(2026, 7, 2), "temp": 32.5},
    ]
    _run(repo.save("+911", temps))
    loaded = _run(repo.load("+911"))

    assert len(loaded) == 2
    assert loaded[0]["date"] == date(2026, 7, 2)
    assert loaded[0]["temp"] == 32.5
    assert "humidity" not in loaded[0]
    assert loaded[1]["date"] == date(2026, 7, 1)
    assert loaded[1]["humidity"] == 70.0


def test_load_unknown_user_returns_empty_list(tmp_path):
    repo = SQLiteRDSStateRepository(str(tmp_path / "t.db"))
    assert _run(repo.load("nobody")) == []


def test_save_caps_at_rds_max_days_newest_kept(tmp_path):
    from prana.config import RDS_MAX_DAYS

    repo = SQLiteRDSStateRepository(str(tmp_path / "t.db"))
    temps = [
        {"date": date(2026, 6, d), "temp": 30.0 + d}
        for d in range(1, RDS_MAX_DAYS + 5)
    ]
    _run(repo.save("+912", temps))
    loaded = _run(repo.load("+912"))

    assert len(loaded) == RDS_MAX_DAYS
    kept_dates = {t["date"] for t in loaded}
    assert date(2026, 6, RDS_MAX_DAYS + 4) in kept_dates
    assert date(2026, 6, 1) not in kept_dates


def test_save_is_idempotent_upsert(tmp_path):
    repo = SQLiteRDSStateRepository(str(tmp_path / "t.db"))
    _run(repo.save("+913", [{"date": date(2026, 7, 1), "temp": 31.0}]))
    _run(repo.save("+913", [{"date": date(2026, 7, 2), "temp": 33.0}]))
    loaded = _run(repo.load("+913"))

    assert len(loaded) == 1
    assert loaded[0]["date"] == date(2026, 7, 2)