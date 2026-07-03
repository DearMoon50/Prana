import math
from prana.recovery.dose_response import minutes_lost, _interp_anchor


def test_cool_night_zero_loss():
    assert minutes_lost(20.0) == 0.0
    assert minutes_lost(18.0) == 0.0


def test_30c_costs_about_14_minutes():
    # Minor et al. 2022 anchor
    assert abs(minutes_lost(30.0) - 14.0) < 0.01


def test_interpolates_between_anchors():
    # halfway between 30C(14) and 33C(22) -> 31.5C -> ~18
    assert abs(minutes_lost(31.5) - 18.0) < 0.5


def test_monotonic_nondecreasing():
    prev = -1.0
    for t in [15, 20, 25, 28, 30, 33, 35, 40, 45, 50]:
        m = minutes_lost(float(t))
        assert m >= prev, f"loss dropped at {t}C"
        prev = m


def test_no_cliff_at_32():
    # sub-threshold heat is NOT zero -- continuous curve, unlike the old 32C cliff
    assert minutes_lost(29.0) > 0.0
    assert minutes_lost(31.0) > minutes_lost(29.0)


def test_humidity_raises_effective_loss():
    # a humid 30C night loses at least as much as a dry 30C night
    dry = minutes_lost(30.0, humidity=30.0)
    humid = minutes_lost(30.0, humidity=90.0)
    assert humid >= dry


def test_hot_climate_multiplier():
    base = minutes_lost(33.0, hot_climate=False)
    boosted = minutes_lost(33.0, hot_climate=True)
    # default multiplier is 1.0 so these are equal unless config changes
    from prana.config import HOT_CLIMATE_SLEEP_MULTIPLIER
    assert abs(boosted - base * HOT_CLIMATE_SLEEP_MULTIPLIER) < 1e-9


def test_bad_input_zero():
    assert minutes_lost(float("nan")) == 0.0
    assert minutes_lost(float("inf")) == 0.0


def test_age_group_adult_baseline_unchanged():
    # Default age_group must match pre-age-sensitivity behavior exactly.
    assert minutes_lost(30.0) == minutes_lost(30.0, age_group="adult")
    assert minutes_lost(30.0, age_group="adult") == 14.0


def test_age_group_older_adult_loses_more_than_adult():
    adult = minutes_lost(30.0, age_group="adult")
    older = minutes_lost(30.0, age_group="older_adult")
    assert older > adult


def test_age_group_ordering_infant_child_adult():
    infant = minutes_lost(30.0, age_group="infant")
    child = minutes_lost(30.0, age_group="child")
    adult = minutes_lost(30.0, age_group="adult")
    assert infant > child > adult


def test_age_group_unknown_defaults_to_adult():
    adult = minutes_lost(30.0, age_group="adult")
    assert minutes_lost(30.0, age_group="unknown_value") == adult
    assert minutes_lost(30.0, age_group=None) == adult
    assert minutes_lost(30.0, age_group="") == adult


def test_age_group_applied_after_hot_climate_multiplier():
    # Both multipliers should compose: hot_climate then age_group, on the
    # same interpolated base value (order documented in dose_response.py).
    from prana.config import HOT_CLIMATE_SLEEP_MULTIPLIER, AGE_GROUP_SLEEP_LOSS_MULTIPLIER
    base = _interp_anchor(30.0)
    expected = base * HOT_CLIMATE_SLEEP_MULTIPLIER * AGE_GROUP_SLEEP_LOSS_MULTIPLIER["older_adult"]
    actual = minutes_lost(30.0, hot_climate=True, age_group="older_adult")
    assert abs(actual - expected) < 1e-9
