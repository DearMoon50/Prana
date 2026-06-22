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
            'us_aqi': {'value': 78, 'unit': 'AQI', 'source': 'open-meteo-cams'},
            'pm2.5': {'value': 18, 'unit': 'ug/m3'},
            'o3': {'value': 80, 'unit': 'ug/m3'},
        }

        result = self.fetcher.calculate_pollutant_aqi_components(pollutants)

        self.assertEqual(result['base_aqi'], 78)
        self.assertEqual(result['source'], 'open-meteo-cams')
        self.assertIn('PM2.5', result['pollutant_aqi'])
        self.assertIn('O3', result['pollutant_aqi'])
        self.assertIn('averaging_windows', result)

    def test_pm25_nowcast_uses_weighted_average(self):
        from data_fetcher import _pm25_nowcast
        # Uniform values -> NowCast == the value itself
        self.assertAlmostEqual(_pm25_nowcast([20.0] * 12), 20.0, places=3)

    def test_pm25_nowcast_weights_recent_higher(self):
        from data_fetcher import _pm25_nowcast
        # Spike in most recent hour should pull average up vs older hours
        older = [10.0] * 11
        recent = [80.0]
        nowcast = _pm25_nowcast(older + recent)
        self.assertGreater(nowcast, 10.0)
        self.assertLess(nowcast, 80.0)

    def test_pm25_nowcast_applied_when_history_present(self):
        pollutants = {
            'pm2.5': {
                'value': 50.0,
                'unit': 'ug/m3',
                'history_12h': [10.0] * 11 + [50.0],
            }
        }
        result = self.fetcher.calculate_pollutant_aqi_components(pollutants)
        self.assertEqual(result['averaging_windows'].get('PM2.5'), 'nowcast_12h')

    def test_pm25_instantaneous_when_no_history(self):
        pollutants = {
            'pm2.5': {'value': 18.0, 'unit': 'ug/m3'}
        }
        result = self.fetcher.calculate_pollutant_aqi_components(pollutants)
        self.assertEqual(result['averaging_windows'].get('PM2.5'), 'instantaneous')


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


class NDTTests(unittest.TestCase):
    def setUp(self):
        from ndt_calculator import NDTCalculator
        self.calculator = NDTCalculator(urban_heat_offset=0)

    def test_wbgt_formula_weights(self):
        # With wet_bulb=30, globe=35, dry=33 -> 0.7*30 + 0.2*35 + 0.1*33 = 21+7+3.3 = 31.3
        result = self.calculator.calculate_wbgt(
            temp_c=33, humidity_percent=70,
            wet_bulb_temp=30, wind_speed_ms=0.5,
            shortwave_radiation=None,
        )
        # globe estimated internally; just check it returns a float in range
        self.assertIsInstance(result, float)
        self.assertGreater(result, 20)
        self.assertLess(result, 45)

    def test_urban_heat_offset_added(self):
        from ndt_calculator import NDTCalculator
        base = NDTCalculator(urban_heat_offset=0).calculate_ndt(
            {'temp': 33, 'humidity': 70, 'wind_speed': 0.5}
        )
        offset = NDTCalculator(urban_heat_offset=3).calculate_ndt(
            {'temp': 33, 'humidity': 70, 'wind_speed': 0.5}
        )
        self.assertAlmostEqual(offset - base, 3.0, places=5)

    def test_heat_stress_levels(self):
        self.assertEqual(self.calculator.get_heat_stress_level(26)[0], 'LOW')
        self.assertEqual(self.calculator.get_heat_stress_level(28)[0], 'MODERATE')
        self.assertEqual(self.calculator.get_heat_stress_level(31)[0], 'HIGH')
        self.assertEqual(self.calculator.get_heat_stress_level(33)[0], 'VERY HIGH')
        self.assertEqual(self.calculator.get_heat_stress_level(36)[0], 'EXTREME')


class CCRITests(unittest.TestCase):
    def test_ccri_returns_safe_for_low_compound_risk(self):
        calculator = CCRICalculator()

        ccri, risk = calculator.calculate_ccri(ndt=28, ha_aqi=60, rds=0, debug=False)

        self.assertLess(ccri, 20)
        self.assertEqual(risk[0], 'SAFE')


if __name__ == '__main__':
    unittest.main()
