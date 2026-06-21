import unittest
from datetime import date, timedelta

from ccri_calculator import CCRICalculator
from data_fetcher import DataFetcher
from ha_aqi_calculator import HAAQICalculator
from rds_calculator import RDSCalculator


class AQIComponentTests(unittest.TestCase):
    def setUp(self):
        self.fetcher = DataFetcher(api_key=None)

    def test_pm25_uses_updated_good_breakpoint(self):
        self.assertAlmostEqual(self.fetcher._calculate_pm25_aqi(9.0), 50.0, places=1)

    def test_provider_us_aqi_preserved_with_components(self):
        pollutants = {
            'us_aqi': {
                'value': 78,
                'unit': 'AQI',
                'source': 'open-meteo-cams',
            },
            'pm2.5': {
                'value': 18,
                'unit': 'ug/m3',
            },
            'o3': {
                'value': 80,
                'unit': 'ug/m3',
            },
        }

        result = self.fetcher.calculate_pollutant_aqi_components(pollutants)

        self.assertEqual(result['base_aqi'], 78)
        self.assertEqual(result['source'], 'open-meteo-cams')
        self.assertIn('PM2.5', result['pollutant_aqi'])
        self.assertIn('O3', result['pollutant_aqi'])


class HeatPollutionRiskTests(unittest.TestCase):
    def setUp(self):
        self.calculator = HAAQICalculator()

    def test_ozone_heat_adjustment_does_not_amplify_pm_driven_base_aqi(self):
        result = self.calculator.calculate_heat_pollution_risk(
            base_aqi=150,
            pollutant_aqi={'PM2.5': 150, 'O3': 60},
            temp_c=35,
        )

        self.assertAlmostEqual(result['ozone_heat_factor'], 1.4, places=2)
        self.assertAlmostEqual(result['ozone_heat_adjusted_aqi'], 84.0, places=1)
        self.assertEqual(result['heat_pollution_risk'], 150)
        self.assertEqual(result['dominant_pollutant'], 'PM2.5')

    def test_ozone_can_drive_heat_pollution_risk_when_adjusted(self):
        result = self.calculator.calculate_heat_pollution_risk(
            base_aqi=95,
            pollutant_aqi={'PM2.5': 70, 'O3': 90},
            temp_c=35,
        )

        self.assertAlmostEqual(result['ozone_heat_adjusted_aqi'], 126.0, places=1)
        self.assertAlmostEqual(result['heat_pollution_risk'], 126.0, places=1)


class RDSTests(unittest.TestCase):
    def test_rds_accumulates_recent_hot_nights_with_decay(self):
        calculator = RDSCalculator()
        today = date.today()
        calculator.add_night_temperature(34.0, today)
        calculator.add_night_temperature(34.0, today - timedelta(days=1))

        rds, consecutive = calculator.calculate_rds()

        self.assertAlmostEqual(rds, 36.0, places=1)
        self.assertEqual(consecutive, 2)

    def test_cool_night_has_zero_recovery_failure(self):
        calculator = RDSCalculator()
        calculator.add_night_temperature(28.0, date.today())

        rds, consecutive = calculator.calculate_rds()

        self.assertEqual(rds, 0.0)
        self.assertEqual(consecutive, 0)


class CCRITests(unittest.TestCase):
    def test_ccri_returns_safe_for_low_compound_risk(self):
        calculator = CCRICalculator()

        ccri, risk = calculator.calculate_ccri(ndt=28, ha_aqi=60, rds=0, debug=False)

        self.assertLess(ccri, 20)
        self.assertEqual(risk[0], 'SAFE')


if __name__ == '__main__':
    unittest.main()
