"""Edge-case hardening tests for RDSCalculator.

Each test captures a real failure mode found by adversarial probing:
invalid temps, future-dated nights, and out-of-range/invalid humidity.
The model must degrade gracefully (skip/clamp), never crash or inflate.
"""
import math
import unittest
from datetime import date, datetime, timedelta

from prana.rds_calculator import RDSCalculator, _rfu_from_excess, _stull_wet_bulb


class TestRFUExtremeHeatDistinguishable(unittest.TestCase):
    """A hard min(100, ...) cap used to make any excess > 10C score
    identically (a 42C and a 58C night were indistinguishable). Fixed with a
    continuous log-tail extension -- these tests pin the fix down."""

    def test_realistic_range_unchanged(self):
        # excess 0-10C (up to 42C effective) must match the original linear
        # model exactly -- this is the entire range used by every existing
        # proof/demo/case-study number in this codebase.
        for excess, expected in [(2, 20.0), (5, 50.0), (8, 80.0), (10, 100.0)]:
            self.assertAlmostEqual(_rfu_from_excess(excess), expected, places=6)

    def test_extreme_values_are_distinguishable(self):
        r42 = _rfu_from_excess(10)   # 42C effective
        r58 = _rfu_from_excess(26)   # 58C effective
        r80 = _rfu_from_excess(48)   # 80C effective
        self.assertLess(r42, r58)
        self.assertLess(r58, r80)

    def test_continuous_at_junction(self):
        # Value and slope must both be continuous at excess=10, so this is a
        # genuine curve continuation, not a discontinuous patch.
        self.assertAlmostEqual(_rfu_from_excess(9.999), _rfu_from_excess(10.001), places=1)
        h = 1e-4
        left_slope = (_rfu_from_excess(10) - _rfu_from_excess(10 - h)) / h
        right_slope = (_rfu_from_excess(10 + h) - _rfu_from_excess(10)) / h
        self.assertAlmostEqual(left_slope, right_slope, places=1)

    def test_negative_and_zero_excess_is_zero(self):
        self.assertEqual(_rfu_from_excess(0), 0.0)
        self.assertEqual(_rfu_from_excess(-5), 0.0)

    def test_extreme_night_still_bounded_at_rds_level(self):
        # Per-night RFU can now exceed 100, but the multi-night RDS total
        # must still be capped at 100 -- the system stays safely bounded.
        calc = RDSCalculator()
        calc.add_night_temperature(80.0, date.today())
        result = calc.calculate_rds()
        self.assertLessEqual(result["rds_mid"], 100.0)
        self.assertTrue(math.isfinite(result["rds_mid"]))


class TestInvalidTemperature(unittest.TestCase):
    def test_none_temp_is_ignored_not_crash(self):
        c = RDSCalculator()
        c.add_night_temperature(None, date.today())
        c.add_night_temperature(34.0, date.today() - timedelta(days=1))
        result = c.calculate_rds()  # must not raise
        # Only the valid 34C night (1 day ago) contributes.
        self.assertGreater(result["rds_mid"], 0.0)
        self.assertTrue(math.isfinite(result["rds_mid"]))

    def test_nan_temp_is_ignored(self):
        c = RDSCalculator()
        c.add_night_temperature(float("nan"), date.today())
        result = c.calculate_rds()
        self.assertEqual(result["rds_mid"], 0.0)
        self.assertEqual(result["consecutive_nights"], 0)

    def test_only_invalid_temps_gives_zero(self):
        c = RDSCalculator()
        c.add_night_temperature(None, date.today())
        c.add_night_temperature(float("nan"), date.today() - timedelta(days=1))
        result = c.calculate_rds()
        self.assertEqual(result["rds_mid"], 0.0)


class TestFutureDatedNight(unittest.TestCase):
    def test_future_night_does_not_inflate(self):
        # A night dated in the future must not produce a decay weight > 1.
        c = RDSCalculator()
        c.add_night_temperature(34.0, date.today() + timedelta(days=3))
        result = c.calculate_rds()
        # RFU(34) = 20 at weight <= 1, so RDS must be <= 20 (not 92.6).
        self.assertLessEqual(result["rds_mid"], 20.0 + 1e-6)
        self.assertTrue(math.isfinite(result["rds_mid"]))

    def test_future_plus_today_bounded(self):
        c = RDSCalculator()
        c.add_night_temperature(34.0, date.today() + timedelta(days=2))
        c.add_night_temperature(34.0, date.today())
        result = c.calculate_rds()
        # Two nights, each RFU 20 at weight <= 1 => at most 40.
        self.assertLessEqual(result["rds_mid"], 40.0 + 1e-6)


class TestInvalidHumidity(unittest.TestCase):
    def test_negative_humidity_no_crash(self):
        self.assertIsNone(_stull_wet_bulb(32, -10))  # guarded, no domain error
        c = RDSCalculator()
        c.add_night_temperature(34.0, date.today(), humidity=-10)
        result = c.calculate_rds()  # must not raise
        self.assertTrue(math.isfinite(result["rds_mid"]))

    def test_nan_humidity_falls_back_to_dry(self):
        c = RDSCalculator()
        c.add_night_temperature(34.0, date.today(), humidity=float("nan"))
        dry_only = RDSCalculator()
        dry_only.add_night_temperature(34.0, date.today())  # no humidity
        self.assertAlmostEqual(
            c.calculate_rds()["rds_mid"], dry_only.calculate_rds()["rds_mid"], places=5
        )

    def test_humidity_above_100_clamped(self):
        # 150% RH must behave identically to 100% RH (clamped), not inflate past it.
        hi = RDSCalculator()
        hi.add_night_temperature(33.0, date.today(), humidity=150)
        clamp = RDSCalculator()
        clamp.add_night_temperature(33.0, date.today(), humidity=100)
        self.assertAlmostEqual(
            hi.calculate_rds()["rds_mid"], clamp.calculate_rds()["rds_mid"], places=5
        )


class TestForecastEstimatorRobustness(unittest.TestCase):
    """Malformed weather-API points must be skipped, never crash the assessment."""

    def setUp(self):
        self.c = RDSCalculator()

    def test_point_missing_temp_is_skipped(self):
        fut = datetime.now() + timedelta(hours=10)
        result = self.c.estimate_nighttime_conditions_from_forecast(
            [{"timestamp": fut}]  # no 'temp'
        )
        self.assertIsNone(result)  # no usable point, but no crash

    def test_point_missing_timestamp_is_skipped(self):
        result = self.c.estimate_nighttime_conditions_from_forecast([{"temp": 30}])
        self.assertIsNone(result)

    def test_mixed_valid_and_malformed(self):
        now = datetime.now()
        good = {"timestamp": now + timedelta(hours=10), "temp": 29.0, "humidity": 70}
        forecast = [
            {"temp": 30},                                   # no timestamp
            {"timestamp": "not-a-datetime", "temp": 31},    # bad timestamp
            {"timestamp": now + timedelta(hours=8), "temp": None},  # bad temp
            {"timestamp": now + timedelta(hours=8), "temp": float("nan")},  # nan temp
            good,
        ]
        result = self.c.estimate_nighttime_conditions_from_forecast(forecast)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["temp"], 29.0, places=5)

    def test_none_and_empty_forecast(self):
        self.assertIsNone(self.c.estimate_nighttime_conditions_from_forecast(None))
        self.assertIsNone(self.c.estimate_nighttime_conditions_from_forecast([]))


class TestBandOrderingHolds(unittest.TestCase):
    """The uncertainty band must stay ordered under every scenario."""

    def _assert_ordered(self, r):
        self.assertLessEqual(r["rds_low"], r["rds_mid"])
        self.assertLessEqual(r["rds_mid"], r["rds_high"])

    def test_ordering_across_scenarios(self):
        scenarios = [
            {"ac": True, "roof_material": "tin", "floor_level": "top"},
            {"ac": True},
            {"roof_material": "tin"},
            {"occupants": 5},
            None,
        ]
        for onb in scenarios:
            c = RDSCalculator(onboarding_data=onb)
            for da, t in [(3, 38.0), (2, 39.0), (1, 30.0), (0, 34.0)]:
                c.add_night_temperature(t, date.today() - timedelta(days=da), humidity=70)
            self._assert_ordered(c.calculate_rds(climate_zone="hot_humid"))

    def test_ordering_with_personalized_offset(self):
        c = RDSCalculator()
        c.add_night_temperature(35.0, date.today(), humidity=60)
        self._assert_ordered(
            c.calculate_rds(personalized_offset=2.5, personalized_band=1.0)
        )


if __name__ == "__main__":
    unittest.main()
