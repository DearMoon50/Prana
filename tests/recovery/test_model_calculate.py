from datetime import date, timedelta
from prana.recovery.model import RecoveryModel


def _seed(m, temps, start=date(2026, 7, 1)):
    for i, t in enumerate(temps):
        m.add_night_temperature(t, date=start + timedelta(days=i))


def test_empty_returns_zero_dict_with_all_keys():
    m = RecoveryModel()
    out = m.calculate_rds()
    for k in ("rds_low", "rds_mid", "rds_high", "consecutive_nights",
              "personalized", "debt_minutes_mid", "tier"):
        assert k in out
    assert out["rds_mid"] == 0.0
    assert out["debt_minutes_mid"] == 0.0
    assert out["tier"] == "LOW"


def test_cool_history_zero_debt():
    m = RecoveryModel()
    _seed(m, [20, 21, 20, 21])
    out = m.calculate_rds()
    assert out["debt_minutes_mid"] == 0.0
    assert out["rds_mid"] == 0.0


def test_hot_history_accumulates_debt():
    m = RecoveryModel()
    _seed(m, [35, 36, 34])
    out = m.calculate_rds()
    assert out["debt_minutes_mid"] > 0
    assert out["rds_mid"] > 0


def test_band_is_ordered():
    m = RecoveryModel()
    _seed(m, [34, 35, 33])
    out = m.calculate_rds()
    assert out["rds_low"] <= out["rds_mid"] <= out["rds_high"]
    assert out["debt_minutes_low"] <= out["debt_minutes_mid"] <= out["debt_minutes_high"]


def test_rds_scale_capped_at_100_by_debt_cap():
    m = RecoveryModel()
    _seed(m, [50, 50, 50, 50, 50, 50, 50])
    out = m.calculate_rds()
    assert out["rds_mid"] == 100.0  # 240-min cap -> 100
    assert out["debt_minutes_mid"] == 240.0


def test_personalized_offset_used():
    m = RecoveryModel()
    _seed(m, [33, 33, 33])
    warm = m.calculate_rds(personalized_offset=2.0)   # hotter room
    cool = m.calculate_rds(personalized_offset=-5.0)  # much cooler room
    assert warm["debt_minutes_mid"] > cool["debt_minutes_mid"]
    assert warm["personalized"] is True


def test_differentiator_hot_vs_cool_history_same_tonight():
    # The core proof: identical cool tonight, opposite history -> different debt.
    hot = RecoveryModel(); _seed(hot, [35, 36, 34, 30])
    cool = RecoveryModel(); _seed(cool, [29, 28, 29, 30])
    assert hot.calculate_rds()["debt_minutes_mid"] > cool.calculate_rds()["debt_minutes_mid"]


def test_older_adult_age_group_produces_higher_debt_than_adult():
    adult = RecoveryModel(age_group="adult")
    older = RecoveryModel(age_group="older_adult")
    _seed(adult, [33, 34, 33])
    _seed(older, [33, 34, 33])
    assert older.calculate_rds()["debt_minutes_mid"] > adult.calculate_rds()["debt_minutes_mid"]


def test_default_age_group_is_adult():
    default = RecoveryModel()
    adult = RecoveryModel(age_group="adult")
    _seed(default, [33, 34, 33])
    _seed(adult, [33, 34, 33])
    assert default.calculate_rds()["debt_minutes_mid"] == adult.calculate_rds()["debt_minutes_mid"]
