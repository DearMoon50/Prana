import math
from prana.recovery.wetbulb import wet_bulb_stull


def test_matches_known_value():
    # 32C at 73% RH -> ~28C wet-bulb (the documented crossover point)
    wb = wet_bulb_stull(32.0, 73.0)
    assert wb is not None
    assert abs(wb - 28.0) < 0.5


def test_rejects_bad_inputs():
    assert wet_bulb_stull(None, 50.0) is None
    assert wet_bulb_stull(30.0, None) is None
    assert wet_bulb_stull(float("nan"), 50.0) is None
    assert wet_bulb_stull(float("inf"), 50.0) is None
    assert wet_bulb_stull(30.0, -5.0) is None


def test_supersaturation_clamped():
    # RH 150 must be treated as 100, not inflate the estimate
    assert wet_bulb_stull(30.0, 150.0) == wet_bulb_stull(30.0, 100.0)
