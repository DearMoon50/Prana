"""
PRANA System - Complete Temperature Calculation Pipeline
Asia's First Compound Climate Emergency Platform

This integrates:
- NDT: Neighbourhood Danger Temperature (WBGT + urban heat island)
- HA-AQI: Heat-Amplified AQI (thermal chemistry correction)
- RDS: Recovery Debt Score (nighttime sleep deprivation tracking)
- CCRI: Compound Climate Risk Index (multiplicative synergistic risk)
"""

from datetime import datetime, timedelta
from data_fetcher import DataFetcher
from ndt_calculator import NDTCalculator
from ha_aqi_calculator import HAAQICalculator
from rds_calculator import RDSCalculator
from ccri_calculator import CCRICalculator
from config import *
from uhi_lookup import lookup_uhi_offset


class PRANASystem:
    def __init__(self, api_key=None, location_name="your ward", urban_heat_offset=None, openaq_api_key=None, onboarding_data=None):
        self.location_name = location_name
        self.onboarding_data = onboarding_data
        if urban_heat_offset is None:
            urban_heat_offset = lookup_uhi_offset(location_name)
        self.data_fetcher = DataFetcher(api_key, openaq_api_key)
        self.ndt_calculator = NDTCalculator(urban_heat_offset)
        self.ha_aqi_calculator = HAAQICalculator()
        self.rds_calculator = RDSCalculator(onboarding_data)
        self.ccri_calculator = CCRICalculator()

        self.current_ndt = None
        self.current_ha_aqi = None
        self.current_rds = None
        self.current_ccri = None
        self.last_update = None

    def update_all(self, lat, lon, sleep_checkin=None, debug=False):
        """
        Update all climate risk metrics.

        Returns:
            Dict with all metrics and alert message
        """
        print(f"\n{'='*60}")
        print(f"PRANA SYSTEM UPDATE - {self.location_name}")
        print(f"{'='*60}\n")

        # Step 1: Fetch current weather
        print("Step 1: Fetching current weather data...")
        weather = self.data_fetcher.get_current_weather(lat, lon)
        if not weather:
            print("[FAIL] Failed to fetch weather data")
            return None
        print(f"[OK] Weather: {weather['temp']:.1f}C, {weather['humidity']:.0f}% humidity")

        # Step 2: Fetch weather forecast
        print("\nStep 2: Fetching weather forecast...")
        forecast = self.data_fetcher.get_forecast(lat, lon, hours=24)
        if not forecast:
            print("[FAIL] Failed to fetch forecast")
            return None
        print(f"[OK] Forecast: {len(forecast)} data points retrieved")

        # Step 3: Calculate NDT
        print("\nStep 3: Calculating NDT (WBGT + urban heat island)...")
        ndt = self.ndt_calculator.calculate_ndt(weather)
        heat_level, heat_desc = self.ndt_calculator.get_heat_stress_level(ndt)
        self.current_ndt = ndt
        print(f"[OK] NDT: {ndt:.1f}C")
        print(f"  Heat Stress: {heat_level} - {heat_desc}")

        # Step 4: Fetch air quality and calculate heat-pollution risk
        print("\nStep 4: Calculating heat-pollution risk (ozone-specific heat adjustment)...")
        pollutants = self.data_fetcher.get_air_quality(lat, lon)
        aqi_components = {
            'base_aqi': None,
            'dominant_pollutant': None,
            'pollutant_aqi': {},
            'source': None
        }
        heat_pollution = None
        base_aqi = None
        oaf = None

        if pollutants:
            aqi_components = self.data_fetcher.calculate_pollutant_aqi_components(pollutants, debug=debug)
            base_aqi = aqi_components['base_aqi']
            if base_aqi:
                heat_pollution = self.ha_aqi_calculator.calculate_heat_pollution_risk(
                    base_aqi, aqi_components['pollutant_aqi'], weather['temp']
                )
                oaf = heat_pollution['ozone_heat_factor']
                ha_aqi = heat_pollution['heat_pollution_risk']
                aqi_category, aqi_desc = self.ha_aqi_calculator.get_aqi_category(ha_aqi)
                self.current_ha_aqi = ha_aqi
                print(f"[OK] Base AQI: {base_aqi:.0f}")
                print(f"[OK] Dominant pollutant: {aqi_components['dominant_pollutant']}")
                print(f"[OK] Ozone heat factor: {oaf:.2f}x at {weather['temp']:.1f}C")
                print(f"[OK] Heat-pollution risk: {ha_aqi:.0f} ({aqi_category})")
                print(f"  {aqi_desc}")
            else:
                self.current_ha_aqi = None
                print("[OK] Could not calculate AQI from available pollutants")
        else:
            self.current_ha_aqi = None
            print("[OK] No air quality data available for this location")

        # Step 5: Calculate RDS
        print("\nStep 5: Calculating RDS (nighttime recovery tracking)...")
        tonight_min = self.rds_calculator.estimate_nighttime_temp_from_forecast(forecast)
        if tonight_min:
            print(f"  Tonight's estimated minimum: {tonight_min:.1f}C")
            self.rds_calculator.add_night_temperature(tonight_min)

        raw_rds, consecutive_nights = self.rds_calculator.calculate_rds(debug=debug)
        rds, rds_adjustment = self.rds_calculator.apply_sleep_checkin_adjustment(raw_rds, sleep_checkin)
        self.current_rds = rds

        rds_message, rds_color = self.rds_calculator.get_rds_message(tonight_min)
        if rds_adjustment['applied']:
            print(f"[OK] RDS adjusted by check-in: {rds_adjustment['delta']:+.1f}")
        print(f"[OK] RDS: {rds:.1f}")
        print(f"  {rds_message}")

        # Step 6: Calculate CCRI
        print("\nStep 6: Calculating CCRI (compound synergistic risk)...")
        ccri, risk_level = self.ccri_calculator.calculate_ccri(ndt, self.current_ha_aqi, rds, debug=debug)
        ccri_components = self.ccri_calculator.calculate_component_scores(ndt, self.current_ha_aqi, rds)
        self.current_ccri = ccri

        level_name, level_desc, level_color = risk_level
        print(f"[OK] CCRI: {ccri:.1f}/100")
        print(f"  Risk Level: {level_name}")
        print(f"  {level_desc}")

        # Step 7: Generate alert
        print("\nStep 7: Generating personalized alert...")
        alert_message = self.ccri_calculator.generate_alert_message(
            ccri, risk_level, ndt, self.current_ha_aqi, rds_message, self.location_name
        )

        self.last_update = datetime.now()

        print(f"\n{'='*60}")
        print("ALERT MESSAGE")
        print(f"{'='*60}\n")
        print(alert_message)
        print(f"\n{'='*60}")
        print(f"Update completed at {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Next update in {UPDATE_INTERVAL} hours")
        print(f"{'='*60}\n")

        result = {
            'timestamp': self.last_update,
            'location': self.location_name,
            'ndt': ndt,
            'heat_level': heat_level,
            'ha_aqi': self.current_ha_aqi,
            'heat_pollution_risk': self.current_ha_aqi,
            'base_aqi': base_aqi,
            'oaf': oaf,
            'ozone_heat_factor': oaf,
            'air_quality_components': aqi_components,
            'heat_pollution': heat_pollution,
            'rds': rds,
            'raw_rds': raw_rds,
            'rds_adjustment': rds_adjustment,
            'consecutive_nights': consecutive_nights,
            'rds_message': rds_message,
            'ccri': ccri,
            'ccri_components': ccri_components,
            'risk_level': level_name,
            'alert_message': alert_message,
            'weather': weather,
            'forecast': forecast,
        }

        result.update(self._build_structured_result(result, weather, pollutants))
        return result

    def get_status_summary(self):
        if not self.last_update:
            return "System not initialized. Run update_all() first."

        age = (datetime.now() - self.last_update).total_seconds() / 3600
        ha_aqi_str = f"{self.current_ha_aqi:.0f}" if self.current_ha_aqi is not None else "N/A"
        return (
            f"\nPRANA System Status - {self.location_name}\n"
            f"Last Updated: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')} ({age:.1f} hours ago)\n\n"
            f"Current Metrics:\n"
            f"- NDT (Heat Stress): {self.current_ndt:.1f}C\n"
            f"- Heat-pollution risk: {ha_aqi_str}\n"
            f"- RDS (Sleep Debt): {self.current_rds:.1f}\n"
            f"- CCRI (Compound Risk): {self.current_ccri:.1f}/100\n\n"
            f"Status: {'UPDATE NEEDED' if age > UPDATE_INTERVAL else 'Current'}\n"
        )

    def add_historical_night_temp(self, night_temp, date):
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()
        self.rds_calculator.add_night_temperature(night_temp, date)
        print(f"Added night temp: {night_temp:.1f}C on {date}")

    def _build_structured_result(self, result, weather, pollutants):
        weather_source = weather.get('source', 'unknown') if weather else 'unknown'
        air_quality_sources = sorted({
            value.get('source', 'unknown')
            for value in pollutants.values()
            if isinstance(value, dict)
        }) if pollutants else []

        confidence = self._estimate_confidence(weather, pollutants)

        return {
            'summary': {
                'title': f"PRANA risk is {result['risk_level']}",
                'location': result['location'],
                'score': round(result['ccri'], 1),
                'risk_level': result['risk_level'],
                'last_updated': result['timestamp'].isoformat(),
                'confidence': confidence,
            },
            'components': {
                'heat': {
                    'label': 'NDT',
                    'description': 'estimated_wbgt_plus_urban_offset',
                    'value': round(result['ndt'], 1),
                    'unit': 'degC',
                    'level': result['heat_level'],
                    'score': round(result['ccri_components']['heat_score'], 1),
                    'confidence': self._estimate_heat_confidence(weather),
                },
                'air_quality': {
                    'label': 'Heat-pollution risk',
                    'value': round(result['heat_pollution_risk'], 1) if result['heat_pollution_risk'] is not None else None,
                    'unit': 'score',
                    'base_aqi': round(result['base_aqi'], 1) if result['base_aqi'] is not None else None,
                    'dominant_pollutant': result['air_quality_components'].get('dominant_pollutant'),
                    'pollutant_aqi': result['air_quality_components'].get('pollutant_aqi', {}),
                    'averaging_windows': result['air_quality_components'].get('averaging_windows', {}),
                    'ozone_heat_factor': round(result['ozone_heat_factor'], 2) if result['ozone_heat_factor'] is not None else None,
                    'ozone_heat_adjusted_aqi': (
                        round(result['heat_pollution']['ozone_heat_adjusted_aqi'], 1)
                        if result.get('heat_pollution') and result['heat_pollution'].get('ozone_heat_adjusted_aqi') is not None
                        else None
                    ),
                    'score': round(result['ccri_components']['pollution_score'], 1),
                    'method': result['heat_pollution'].get('method') if result.get('heat_pollution') else None,
                    'confidence': result['heat_pollution'].get('pollution_confidence') if result.get('heat_pollution') else 'LOW',
                },
                'recovery': {
                    'label': 'RDS',
                    'description': 'outdoor_nighttime_recovery_risk_proxy',
                    'value': round(result['rds'], 1),
                    'raw_value': round(result['raw_rds'], 1),
                    'unit': 'score',
                    'score': round(result['ccri_components']['recovery_score'], 1),
                    'consecutive_hot_nights': result['consecutive_nights'],
                    'adjustment': result['rds_adjustment'],
                    'message': result['rds_message'],
                    'confidence': self.rds_calculator.estimate_recovery_confidence(
                        result['rds_adjustment'] if result['rds_adjustment']['applied'] else None
                    ),
                },
                'compound': {
                    'label': 'CCRI',
                    'value': round(result['ccri'], 1),
                    'unit': 'score',
                    'heat_score': round(result['ccri_components']['heat_score'], 1),
                    'pollution_score': round(result['ccri_components']['pollution_score'], 1),
                    'recovery_score': round(result['ccri_components']['recovery_score'], 1),
                    'base_ccri': round(result['ccri_components']['base_ccri'], 1),
                    'recovery_multiplier': round(result['ccri_components']['recovery_multiplier'], 2),
                    'confidence': confidence,
                },
            },
            'sources': {
                'weather': weather_source,
                'air_quality': air_quality_sources,
                'weather_fields': {
                    'wet_bulb_temp': weather.get('wet_bulb_temp') if weather else None,
                    'shortwave_radiation': weather.get('shortwave_radiation') if weather else None,
                },
            },
            'confidence': confidence,
        }

    def _estimate_confidence(self, weather, pollutants):
        if not weather:
            return 'LOW'
        score = 1
        if weather.get('wet_bulb_temp') is not None:
            score += 1
        if weather.get('shortwave_radiation') is not None:
            score += 1
        if pollutants:
            score += 1
        if pollutants and any(
            isinstance(value, dict) and value.get('source') == 'openaq'
            for value in pollutants.values()
        ):
            score += 1
        if score >= 4:
            return 'HIGH'
        if score >= 2:
            return 'MEDIUM'
        return 'LOW'

    def _estimate_heat_confidence(self, weather):
        if not weather:
            return 'LOW'
        score = 1
        if weather.get('wet_bulb_temp') is not None:
            score += 1
        if weather.get('shortwave_radiation') is not None:
            score += 1
        if score >= 3:
            return 'HIGH'
        if score >= 2:
            return 'MEDIUM'
        return 'LOW'


def demo_prana_system():
    print("\n" + "="*60)
    print("PRANA SYSTEM DEMO")
    print("Asia's First Compound Climate Emergency Platform")
    print("="*60 + "\n")

    try:
        from location_detector import get_current_location, get_location_name
        location = get_current_location()
        lat, lon = location['lat'], location['lon']
        location_name = get_location_name(location)
    except Exception as e:
        print(f"WARNING: Location detection failed: {e}")
        print("Using Chennai as default...\n")
        lat, lon = 13.0827, 80.2707
        location_name = "Chennai, India"

    prana = PRANASystem(
        api_key=OPENWEATHER_API_KEY,
        location_name=location_name,
        urban_heat_offset=3.0,
    )

    print("Adding historical nighttime temperatures for RDS tracking...")
    today = datetime.now().date()
    prana.add_historical_night_temp(34.5, today - timedelta(days=3))
    prana.add_historical_night_temp(35.2, today - timedelta(days=2))
    prana.add_historical_night_temp(36.1, today - timedelta(days=1))
    print()

    result = prana.update_all(lat, lon)

    if result:
        print("\n[OK] PRANA system operational")
    else:
        print("\n[FAIL] System update failed - check API keys and network connection")


if __name__ == "__main__":
    demo_prana_system()
