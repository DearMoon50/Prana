import math
from datetime import date
from prana.recovery.model import RecoveryModel


def test_rejects_non_numeric_temp():
    m = RecoveryModel()
    m.add_night_temperature(None, date=date(2026, 7, 1))
    m.add_night_temperature(float("nan"), date=date(2026, 7, 1))
    assert m.nighttime_temps == []


def test_dedupe_by_date_updates_in_place():
    m = RecoveryModel()
    m.add_night_temperature(30.0, date=date(2026, 7, 1))
    m.add_night_temperature(33.0, date=date(2026, 7, 1), humidity=70)
    assert len(m.nighttime_temps) == 1
    assert m.nighttime_temps[0]["temp"] == 33.0
    assert m.nighttime_temps[0]["humidity"] == 70


def test_window_trims_to_config_window():
    from prana.config import RECOVERY_WINDOW_NIGHTS
    m = RecoveryModel()
    for d in range(1, RECOVERY_WINDOW_NIGHTS + 4):
        m.add_night_temperature(30.0, date=date(2026, 7, d))
    assert len(m.nighttime_temps) == RECOVERY_WINDOW_NIGHTS


def test_static_offset_helpers_delegate():
    # backend/main.py calls these as staticmethods
    assert RecoveryModel.compute_onboarding_temp_offset(None) == 0.0
    assert RecoveryModel.compute_band_width({}) > 0


def test_classify_tier():
    m = RecoveryModel()
    assert m.classify_tier(0.0) == "LOW"
    assert m.classify_tier(45.0) == "MODERATE"
    assert m.classify_tier(120.0) == "HIGH"
    assert m.classify_tier(200.0) == "SEVERE"


def test_age_group_constructor_defaults_to_adult():
    m = RecoveryModel()
    assert m.age_group == "adult"


def test_age_group_constructor_accepts_explicit_value():
    m = RecoveryModel(age_group="older_adult")
    assert m.age_group == "older_adult"


def test_age_group_invalid_values_stored_as_is_but_behave_as_adult():
    # Storage doesn't normalize; behavior normalizes at minutes_lost() call time.
    for bad in (None, "", "invalid_value"):
        m = RecoveryModel(age_group=bad)
        m.add_night_temperature(30.0)
        adult = RecoveryModel(age_group="adult")
        adult.add_night_temperature(30.0)
        assert m.calculate_rds()["debt_minutes_mid"] == adult.calculate_rds()["debt_minutes_mid"]
