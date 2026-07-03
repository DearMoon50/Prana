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
