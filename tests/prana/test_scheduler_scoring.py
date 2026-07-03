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


def test_cycle_once_passes_history_and_personalization(monkeypatch):
    captured = {}

    class FakeRDSRepo:
        async def load(self, user_id):
            return [{"date": date(2026, 7, 1), "temp": 33.0}]

    class FakeCheckinRepo:
        async def list_for_user(self, user_id, limit=30):
            return [{"checkin_date": "2026-07-01", "sleep_quality": "good"}]

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

    async def fake_get_risk(*, ctx, historical_temps=None, personalization=None):
        captured["historical_temps"] = historical_temps
        captured["personalization"] = personalization
        return {
            "ccri": 50.0,
            "risk_level": "HIGH",
            "ndt": 30.0,
            "rds_mid": 40.0,
            "consecutive_nights": 3,
            "alert_message": "x",
            "as_of": "2026-07-03T00:00:00",
        }

    monkeypatch.setattr(scheduler, "build_repo", lambda: object())
    monkeypatch.setattr(scheduler, "build_messaging", lambda: object())
    monkeypatch.setattr(scheduler, "build_rds_repo", lambda: FakeRDSRepo())
    monkeypatch.setattr(scheduler, "build_checkin_repo", lambda: FakeCheckinRepo())
    monkeypatch.setattr(scheduler, "run_alert_cycle", fake_run_alert_cycle)
    monkeypatch.setattr(scheduler, "get_risk", fake_get_risk)

    out = asyncio.run(scheduler._cycle_once())

    assert out == 1
    assert captured["historical_temps"] == [{"date": date(2026, 7, 1), "temp": 33.0}]
    assert captured["personalization"] is not None