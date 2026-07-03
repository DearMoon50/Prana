from datetime import date, timedelta
from prana.prana_system import PRANASystem


def test_system_uses_recovery_model():
    from prana.recovery.model import RecoveryModel
    sys = PRANASystem(location_name="Chennai")
    assert isinstance(sys.rds_calculator, RecoveryModel)


def test_pipeline_rds_block_returns_debt_keys(monkeypatch):
    sys = PRANASystem(location_name="Chennai")
    # seed a hot history directly on the recovery model
    for i, t in enumerate([35, 36, 34]):
        sys.rds_calculator.add_night_temperature(t, date=date(2026, 7, 1) + timedelta(days=i))
    out = sys.rds_calculator.calculate_rds(climate_zone=sys.climate_zone)
    assert "debt_minutes_mid" in out and "rds_mid" in out and "tier" in out
