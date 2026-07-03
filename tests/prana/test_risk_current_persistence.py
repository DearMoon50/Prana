import asyncio
from datetime import date

from fastapi.testclient import TestClient

import backend.main as main
from backend.main import app
from framework.persistence.sqlite import (
    SQLiteCheckinRepository,
    SQLiteRDSStateRepository,
    SQLiteRiskEvalRepository,
    SQLiteUserRepository,
)


def _register(client, phone="+919900010001"):
    return client.post(
        "/register",
        json={
            "phone": phone,
            "location_name": "Chennai",
            "lat": 13.08,
            "lon": 80.27,
            "urban_heat_offset": None,
            "onboarding": {"ac": True, "roof_material": "concrete", "floor_level": "top"},
        },
    )


def test_risk_current_persists_rds_window_and_eval(monkeypatch, tmp_path):
    db_path = str(tmp_path / "t.db")
    main.user_repo = SQLiteUserRepository(db_path)
    main.checkin_repo = SQLiteCheckinRepository(db_path)
    main.rds_repo = SQLiteRDSStateRepository(db_path)
    main.risk_eval_repo = SQLiteRiskEvalRepository(db_path)

    def fake_pipeline(payload, personalization=None, historical_temps=None):
        result = {
            "raw_temp": 31.0,
            "raw_humidity": 70.0,
            "aqi": {"base_aqi": 120.0},
            "ndt": 34.6,
            "rds": {"rds_mid": 66.1},
            "ccri": 64.7,
            "rds_historical_temps": [{"date": date(2026, 7, 2), "temp": 31.0}],
        }
        return result, "log"

    monkeypatch.setattr(main, "_run_prana_pipeline", fake_pipeline)

    client = TestClient(app)
    phone = "+919900010002"
    assert _register(client, phone).status_code == 200

    resp = client.post(
        "/risk/current",
        json={"lat": 13.08, "lon": 80.27, "location_name": "Chennai", "user_id": phone},
    )
    assert resp.status_code == 200

    async def loads():
        window = await main.rds_repo.load(phone)
        evals = await main.risk_eval_repo.list_for_user(phone)
        return window, evals

    window, evals = asyncio.run(loads())
    assert len(window) == 1
    assert window[0]["temp"] == 31.0
    assert len(evals) == 1
    assert evals[0]["ccri"] == 64.7
    assert evals[0]["rds_mid"] == 66.1