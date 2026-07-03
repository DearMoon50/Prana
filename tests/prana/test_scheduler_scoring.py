import asyncio
from datetime import date

from framework.context.user import UserContext

import prana.scheduler as scheduler
from prana.ai_tools import risk as risk_mod


def test_get_risk_seeds_historical_temps(monkeypatch):
    captured = {}

    class FakeSystem:
        def __init__(self, **kwargs):
            self.rds_calculator = type("RC", (), {"nighttime_temps": []})()

        def update_all(self, lat, lon, personalization=None):
            captured["seeded"] = list(self.rds_calculator.nighttime_temps)
            captured["personalization"] = personalization
            return {
                "ccri": 50.0,
                "risk_level": "HIGH",
                "ndt": 30.0,
                "rds": {"rds_mid": 40.0, "consecutive_nights": 3},
                "alert_message": "x",
                "timestamp": "2026-07-03T00:00:00",
            }

    monkeypatch.setattr(risk_mod, "PRANASystem", FakeSystem)

    ctx = UserContext(
        user_id="+911",
        phone="+911",
        metadata={"lat": 13.0, "lon": 80.0, "location_name": "Chennai"},
    )
    hist = [{"date": date(2026, 7, 1), "temp": 33.0}]
    out = asyncio.run(
        risk_mod.get_risk(
            ctx=ctx,
            historical_temps=hist,
            personalization={"offset": -3.0, "band": 2.0, "n_checkins": 5},
        )
    )

    assert out["risk_level"] == "HIGH"
    assert captured["seeded"] == hist
    assert captured["personalization"] == {
        "offset": -3.0,
        "band": 2.0,
        "n_checkins": 5,
    }


def test_cycle_once_records_risk_eval_and_persists_rds_state(monkeypatch):
    captured = {}

    class FakeRDSRepo:
        async def save(self, user_id, nighttime_temps):
            captured["saved_user_id"] = user_id
            captured["saved_temps"] = nighttime_temps

    class FakeRiskEvalRepo:
        async def add(self, user_id, **kwargs):
            captured["eval_user_id"] = user_id
            captured["eval_kwargs"] = kwargs

    async def fake_run_alert_cycle(repo, messaging, risk_fn):
        user = UserContext(
            user_id="+911",
            phone="+911",
            metadata={
                "lat": 13.0,
                "lon": 80.0,
                "location_name": "Chennai",
                "onboarding": {"ac": True, "roof_material": "concrete", "floor_level": "top"},
            },
        )
        captured["result"] = await risk_fn(user)
        return 1

    new_hist = [{"date": date(2026, 7, 2), "temp": 34.0}]

    async def fake_get_risk(*, ctx):
        # score() now delegates entirely to get_risk's self-loading -- it is
        # called with only ctx, no explicit historical_temps/personalization.
        captured["get_risk_ctx"] = ctx
        return {
            "ccri": 50.0,
            "risk_level": "HIGH",
            "ndt": 30.0,
            "rds_mid": 40.0,
            "consecutive_nights": 3,
            "alert_message": "x",
            "as_of": "2026-07-03T00:00:00",
            "weather": {"temp": 33.0, "humidity": 80.0},
            "base_aqi": 90.0,
            "rds_historical_temps": new_hist,
        }

    monkeypatch.setattr(scheduler, "build_repo", lambda: object())
    monkeypatch.setattr(scheduler, "build_messaging", lambda: object())
    monkeypatch.setattr(scheduler, "build_rds_repo", lambda: FakeRDSRepo())
    monkeypatch.setattr(scheduler, "build_risk_eval_repo", lambda: FakeRiskEvalRepo())
    monkeypatch.setattr(scheduler, "run_alert_cycle", fake_run_alert_cycle)
    monkeypatch.setattr(scheduler, "get_risk", fake_get_risk)

    out = asyncio.run(scheduler._cycle_once())

    assert out == 1
    # score() delegates self-loading to get_risk, no manual history/personalization
    assert captured["get_risk_ctx"].user_id == "+911"
    # risk evaluation is recorded from the result
    assert captured["eval_user_id"] == "+911"
    assert captured["eval_kwargs"]["rds_mid"] == 40.0
    assert captured["eval_kwargs"]["ccri"] == 50.0
    assert captured["eval_kwargs"]["outdoor_temp"] == 33.0
    # updated RDS state is persisted for the next cycle
    assert captured["saved_user_id"] == "+911"
    assert captured["saved_temps"] == new_hist


def test_cycle_once_skips_persistence_on_error(monkeypatch):
    captured = {"save_called": False}

    class FakeRDSRepo:
        async def save(self, user_id, nighttime_temps):
            captured["save_called"] = True

    class FakeRiskEvalRepo:
        async def add(self, user_id, **kwargs):
            captured["add_called"] = True

    async def fake_run_alert_cycle(repo, messaging, risk_fn):
        user = UserContext(user_id="+911", phone="+911", metadata={"lat": 13.0, "lon": 80.0})
        return await risk_fn(user)

    async def fake_get_risk(*, ctx):
        return {"error": "Risk data is temporarily unavailable."}

    monkeypatch.setattr(scheduler, "build_repo", lambda: object())
    monkeypatch.setattr(scheduler, "build_messaging", lambda: object())
    monkeypatch.setattr(scheduler, "build_rds_repo", lambda: FakeRDSRepo())
    monkeypatch.setattr(scheduler, "build_risk_eval_repo", lambda: FakeRiskEvalRepo())
    monkeypatch.setattr(scheduler, "run_alert_cycle", fake_run_alert_cycle)
    monkeypatch.setattr(scheduler, "get_risk", fake_get_risk)

    out = asyncio.run(scheduler._cycle_once())

    assert out == {"error": "Risk data is temporarily unavailable."}
    assert captured["save_called"] is False
    assert "add_called" not in captured