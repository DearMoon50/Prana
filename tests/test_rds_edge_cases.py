"""Edge-case hardening tests for RecoveryModel (migrated from RDSCalculator, Task 12).

Each test captures a real failure mode found by adversarial probing:
invalid temps, future-dated nights, and out-of-range/invalid humidity.
The model must degrade gracefully (skip/clamp), never crash or inflate.

NOTE on deletion: the TestRFUExtremeHeatDistinguishable class (and the
`_rfu_from_excess` helper it tested) is intentionally REMOVED here, not
migrated. That helper implemented the old per-night RFU log-tail extension
(a continuous continuation of the linear RFU-per-degC formula past a 10C
excess threshold, so 42C/58C/80C nights stayed distinguishable). The
sleep-debt-ledger rebuild replaces RFU entirely with the Minor-2022-anchored
`minutes_lost` dose-response curve (prana.recovery.dose_response), which has
no linear-then-log-tail shape and no 10C junction to be continuous at -- so
those tests no longer describe anything that exists. Their actual intent
(bounded, distinguishable behavior under extreme heat) is preserved by
tests/recovery/test_dose_response.py and the ledger-cap tests in
tests/recovery/test_ledger.py and test_model_calculate.py
(test_rds_scale_capped_at_100_by_debt_cap), which assert the new curve is
monotonic and the multi-night debt is bounded at RECOVERY_DEBT_CAP_MIN.
"""
import math
import unittest
from datetime import date, datetime, timedelta

from prana.recovery.model import RecoveryModel
from prana.recovery.wetbulb import wet_bulb_stull


class TestInvalidTemperature(unittest.TestCase):
    def test_none_temp_is_ignored_not_crash(self):
        c = RecoveryModel()
        c.add_night_temperature(None, date.today())
        c.add_night_temperature(34.0, date.today() - timedelta(days=1))
        result = c.calculate_rds()  # must not raise
        # Only the valid 34C night (1 day ago) contributes.
        self.assertGreater(result["rds_mid"], 0.0)
        self.assertTrue(math.isfinite(result["rds_mid"]))

    def test_nan_temp_is_ignored(self):
        c = RecoveryModel()
        c.add_night_temperature(float("nan"), date.today())
        result = c.calculate_rds()
        self.assertEqual(result["rds_mid"], 0.0)
        self.assertEqual(result["consecutive_nights"], 0)

    def test_only_invalid_temps_gives_zero(self):
        c = RecoveryModel()
        c.add_night_temperature(None, date.today())
        c.add_night_temperature(float("nan"), date.today() - timedelta(days=1))
        result = c.calculate_rds()
        self.assertEqual(result["rds_mid"], 0.0)


class TestFutureDatedNight(unittest.TestCase):
    def test_future_night_does_not_inflate(self):
        # A night dated in the future must not produce extra debt beyond
        # what that single night's own dose-response contributes.
        c = RecoveryModel()
        c.add_night_temperature(34.0, date.today() + timedelta(days=3))
        result = c.calculate_rds()
        solo = RecoveryModel()
        solo.add_night_temperature(34.0, date.today())
        self.assertAlmostEqual(result["debt_minutes_mid"], solo.calculate_rds()["debt_minutes_mid"], places=5)
        self.assertTrue(math.isfinite(result["rds_mid"]))

    def test_future_plus_today_bounded(self):
        c = RecoveryModel()
        c.add_night_temperature(34.0, date.today() + timedelta(days=2))
        c.add_night_temperature(34.0, date.today())
        result = c.calculate_rds()
        # Bounded by the debt cap regardless of future-dating.
        self.assertLessEqual(result["debt_minutes_mid"], 240.0 + 1e-6)
        self.assertTrue(math.isfinite(result["rds_mid"]))


class TestInvalidHumidity(unittest.TestCase):
    def test_negative_humidity_no_crash(self):
        self.assertIsNone(wet_bulb_stull(32, -10))  # guarded, no domain error
        c = RecoveryModel()
        c.add_night_temperature(34.0, date.today(), humidity=-10)
        result = c.calculate_rds()  # must not raise
        self.assertTrue(math.isfinite(result["rds_mid"]))

    def test_nan_humidity_falls_back_to_dry(self):
        c = RecoveryModel()
        c.add_night_temperature(34.0, date.today(), humidity=float("nan"))
        dry_only = RecoveryModel()
        dry_only.add_night_temperature(34.0, date.today())  # no humidity
        self.assertAlmostEqual(
            c.calculate_rds()["rds_mid"], dry_only.calculate_rds()["rds_mid"], places=5
        )

    def test_humidity_above_100_clamped(self):
        # 150% RH must behave identically to 100% RH (clamped), not inflate past it.
        hi = RecoveryModel()
        hi.add_night_temperature(33.0, date.today(), humidity=150)
        clamp = RecoveryModel()
        clamp.add_night_temperature(33.0, date.today(), humidity=100)
        self.assertAlmostEqual(
            hi.calculate_rds()["rds_mid"], clamp.calculate_rds()["rds_mid"], places=5
        )


class TestForecastEstimatorRobustness(unittest.TestCase):
    """Malformed weather-API points must be skipped, never crash the assessment."""

    def setUp(self):
        self.c = RecoveryModel()

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
            c = RecoveryModel(onboarding_data=onb)
            for da, t in [(3, 38.0), (2, 39.0), (1, 30.0), (0, 34.0)]:
                c.add_night_temperature(t, date.today() - timedelta(days=da), humidity=70)
            self._assert_ordered(c.calculate_rds(climate_zone="hot_humid"))

    def test_ordering_with_personalized_offset(self):
        c = RecoveryModel()
        c.add_night_temperature(35.0, date.today(), humidity=60)
        self._assert_ordered(
            c.calculate_rds(personalized_offset=2.5, personalized_band=1.0)
        )


if __name__ == "__main__":
    unittest.main()
