"""Test Issue 1 fix: RDS uncertainty bands.

Migrated to RecoveryModel (Task 12): the band mechanics (low <= mid <= high,
range shown in the message when tiers differ) carry over unchanged; only the
underlying score is now debt-minutes rather than the old RFU-decay score."""

import unittest
from datetime import datetime, timedelta
from prana.recovery.model import RecoveryModel


class TestIssue1RDSUncertaintyBands(unittest.TestCase):
    def setUp(self):
        self.calculator = RecoveryModel()
        today = datetime.now().date()
        # Add some hot nights
        self.calculator.add_night_temperature(35.0, today - timedelta(days=2))
        self.calculator.add_night_temperature(36.0, today - timedelta(days=1))
        self.calculator.add_night_temperature(34.0, today)
    
    def test_rds_returns_dict_with_low_mid_high(self):
        """calculate_rds should return dict with rds_low, rds_mid, rds_high"""
        result = self.calculator.calculate_rds()
        
        self.assertIsInstance(result, dict)
        self.assertIn('rds_low', result)
        self.assertIn('rds_mid', result)
        self.assertIn('rds_high', result)
        self.assertIn('consecutive_nights', result)
    
    def test_rds_low_less_than_mid_less_than_high_ac_only(self):
        """RDS low <= mid <= high for AC onboarding"""
        onboarding = {'ac': True}  # -3°C offset
        result = self.calculator.calculate_rds(onboarding_data=onboarding)
        
        self.assertLessEqual(result['rds_low'], result['rds_mid'],
                            "rds_low must be <= rds_mid")
        self.assertLessEqual(result['rds_mid'], result['rds_high'],
                            "rds_mid must be <= rds_high")
    
    def test_rds_low_less_than_mid_less_than_high_tin_roof(self):
        """RDS low <= mid <= high for tin roof onboarding"""
        onboarding = {'roof_material': 'tin'}  # +2°C offset
        result = self.calculator.calculate_rds(onboarding_data=onboarding)
        
        self.assertLessEqual(result['rds_low'], result['rds_mid'])
        self.assertLessEqual(result['rds_mid'], result['rds_high'])
    
    def test_rds_low_less_than_mid_less_than_high_ac_top_floor(self):
        """RDS low <= mid <= high for AC + top floor"""
        onboarding = {'ac': True, 'floor_level': 'top'}  # AC now temp-dependent (ASHRAE curve); top-floor default offset is 0
        result = self.calculator.calculate_rds(onboarding_data=onboarding)
        
        self.assertLessEqual(result['rds_low'], result['rds_mid'])
        self.assertLessEqual(result['rds_mid'], result['rds_high'])
    
    def test_get_rds_message_shows_range_when_band_wide(self):
        """Message should show a numeric min/max range when the low-high
        debt-minutes band is wide (> 15 min, per RecoveryModel.get_rds_message)."""
        today = datetime.now().date()
        calc = RecoveryModel({'roof_material': 'tin', 'floor_level': 'top'})  # wide band
        calc.add_night_temperature(38.0, today - timedelta(days=1))
        calc.add_night_temperature(39.0, today)

        rds_dict = calc.calculate_rds()
        message, color = calc.get_rds_message(rds_dict, 39.0)

        self.assertIsInstance(message, str)
        if rds_dict['debt_minutes_high'] - rds_dict['debt_minutes_low'] > 15:
            self.assertIn('range', message.lower())
            self.assertIn('min', message.lower())

    def test_get_rds_message_single_value_when_band_narrow(self):
        """Message should not show a range when low/high are close together."""
        today = datetime.now().date()
        calc = RecoveryModel()
        calc.add_night_temperature(20.0, today)  # Cool temp -> zero debt, narrow band

        rds_dict = calc.calculate_rds()
        message, color = calc.get_rds_message(rds_dict, 20.0)

        self.assertIsInstance(message, str)
        self.assertGreater(len(message), 10)
        self.assertNotIn('range', message.lower())


if __name__ == '__main__':
    unittest.main()
