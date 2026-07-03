import asyncio

from framework.persistence.sqlite import SQLiteRiskEvalRepository


def _run(coro):
    return asyncio.run(coro)


def test_add_then_list_returns_row(tmp_path):
    repo = SQLiteRiskEvalRepository(str(tmp_path / "t.db"))
    _run(
        repo.add(
            "+911",
            outdoor_temp=31.0,
            outdoor_humidity=70.0,
            base_aqi=120.0,
            ndt=34.6,
            rds_mid=66.1,
            ccri=64.7,
        )
    )
    rows = _run(repo.list_for_user("+911"))
    assert len(rows) == 1
    row = rows[0]
    assert row["outdoor_temp"] == 31.0
    assert row["ndt"] == 34.6
    assert row["rds_mid"] == 66.1
    assert row["ccri"] == 64.7
    assert row["timestamp"]


def test_list_newest_first_and_limit(tmp_path):
    repo = SQLiteRiskEvalRepository(str(tmp_path / "t.db"))
    for ccri in (10.0, 20.0, 30.0):
        _run(
            repo.add(
                "+912",
                outdoor_temp=None,
                outdoor_humidity=None,
                base_aqi=None,
                ndt=None,
                rds_mid=None,
                ccri=ccri,
            )
        )
    rows = _run(repo.list_for_user("+912", limit=2))
    assert len(rows) == 2
    assert rows[0]["ccri"] == 30.0


def test_list_unknown_user_empty(tmp_path):
    repo = SQLiteRiskEvalRepository(str(tmp_path / "t.db"))
    assert _run(repo.list_for_user("nobody")) == []