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


class PRANASystem:
    def __init__(self, api_key=None, location_name="your ward", urban_heat_offset=3.0, openaq_api_key=None):
        """
        Initialize PRANA Climate Risk System
        
        Args:
            api_key: Optional OpenWeatherMap API key used only as fallback
            location_name: Name of the ward/neighborhood
            urban_heat_offset: Urban heat island effect offset (C)
                             Typically 2-4C for low-income wards vs airport
            openaq_api_key: OpenAQ API key (v3 requires key, get from openaq.org)
        """
        self.location_name = location_name
        self.data_fetcher = DataFetcher(api_key, openaq_api_key)
        self.ndt_calculator = NDTCalculator(urban_heat_offset)
        self.ha_aqi_calculator = HAAQICalculator()
        self.rds_calculator = RDSCalculator()
        self.ccri_calculator = CCRICalculator()
        
        # Store current state
        self.current_ndt = None
        self.current_ha_aqi = None
        self.current_rds = None
        self.current_ccri = None
        self.last_update = None
    
    def update_all(self, lat, lon):
        """
        Update all climate risk metrics
        
        Complete pipeline:
        1. Fetch current weather + forecast
        2. Fetch air quality data
        3. Calculate NDT (heat stress)
        4. Calculate HA-AQI (thermal chemistry amplification)
        5. Update RDS (sleep deprivation tracking)
        6. Calculate CCRI (compound risk)
        
        Args:
            lat: Latitude
            lon: Longitude
        
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
            print("[OK] Failed to fetch weather data")
            return None
        print(f"[OK] Weather: {weather['temp']:.1f}C, {weather['humidity']:.0f}% humidity")
        
        # Step 2: Fetch weather forecast
        print("\nStep 2: Fetching weather forecast...")
        forecast = self.data_fetcher.get_forecast(lat, lon, hours=24)
        if not forecast:
            print("[OK] Failed to fetch forecast")
            return None
        print(f"[OK] Forecast: {len(forecast)} data points retrieved")
        
        # Step 3: Calculate NDT (Neighbourhood Danger Temperature)
        print("\nStep 3: Calculating NDT (WBGT + urban heat island)...")
        ndt = self.ndt_calculator.calculate_ndt(weather)
        heat_level, heat_desc = self.ndt_calculator.get_heat_stress_level(ndt)
        self.current_ndt = ndt
        print(f"[OK] NDT: {ndt:.1f}C")
        print(f"  Heat Stress: {heat_level} - {heat_desc}")
        
        # Step 4: Fetch air quality and calculate HA-AQI
        print("\nStep 4: Calculating HA-AQI (heat-amplified air quality)...")
        pollutants = self.data_fetcher.get_air_quality(lat, lon)
        aqi_components = {
            'base_aqi': None,
            'dominant_pollutant': None,
            'pollutant_aqi': {},
            'source': None
        }
        heat_pollution = None
        
        if pollutants:
            aqi_components = self.data_fetcher.calculate_pollutant_aqi_components(pollutants, debug=True)
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
                
                # Forecast HA-AQI for next 6 hours
                print("\n  Forecasting HA-AQI for next 6 hours...")
                ha_forecast = self.ha_aqi_calculator.forecast_ha_aqi(base_aqi, forecast[:2])
                if ha_forecast:
                    for item in ha_forecast:
                        print(f"  {item['timestamp'].strftime('%H:%M')}: "
                              f"Temp {item['temp']:.1f}C -> HA-AQI {item['ha_aqi']:.0f} "
                              f"(OAF: {item['oaf']:.2f}x)")
            else:
                self.current_ha_aqi = None
                print("[OK] Could not calculate AQI from available pollutants")
        else:
            self.current_ha_aqi = None
            print("[OK] No air quality data available for this location")
        
        # Step 5: Calculate RDS (Recovery Debt Score)
        print("\nStep 5: Calculating RDS (nighttime recovery tracking)...")
        
        # Estimate tonight's minimum temperature from forecast
        tonight_min = self.rds_calculator.estimate_nighttime_temp_from_forecast(forecast)
        if tonight_min:
            print(f"  Tonight's estimated minimum: {tonight_min:.1f}C")
            self.rds_calculator.add_night_temperature(tonight_min)
        
        # Calculate cumulative RDS
        rds, consecutive_nights = self.rds_calculator.calculate_rds(debug=True)
        self.current_rds = rds
        
        # Get range-based RDS message
        rds_message, rds_color = self.rds_calculator.get_rds_message(tonight_min)
        print(f"[OK] RDS: {rds:.1f}")
        print(f"  {rds_message}")
        
        # Step 6: Calculate CCRI (Compound Climate Risk Index)
        print("\nStep 6: Calculating CCRI (compound synergistic risk)...")
        ccri, risk_level = self.ccri_calculator.calculate_ccri(ndt, self.current_ha_aqi, rds)
        self.current_ccri = ccri
        
        level_name, level_desc, level_color = risk_level
        print(f"[OK] CCRI: {ccri:.1f}/100")
        print(f"  Risk Level: {level_name}")
        print(f"  {level_desc}")
        
        # Step 7: Generate personalized alert message
        print("\nStep 7: Generating personalized alert...")
        alert_message = self.ccri_calculator.generate_alert_message(
            ccri, risk_level, ndt, self.current_ha_aqi, rds_message, self.location_name
        )
        
        self.last_update = datetime.now()
        
        # Print full alert
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
            'base_aqi': base_aqi if pollutants else None,
            'oaf': oaf if pollutants and base_aqi else None,
            'ozone_heat_factor': oaf if pollutants and base_aqi else None,
            'air_quality_components': aqi_components,
            'heat_pollution': heat_pollution,
            'rds': rds,
            'consecutive_nights': consecutive_nights,
            'rds_message': rds_message,
            'ccri': ccri,
            'risk_level': level_name,
            'alert_message': alert_message,
            'weather': weather,
            'forecast': forecast
        }

        result.update(self._build_structured_result(result, weather, pollutants))
        return result
    
    def get_status_summary(self):
        """Get current status summary"""
        if not self.last_update:
            return "System not initialized. Run update_all() first."
        
        age = (datetime.now() - self.last_update).total_seconds() / 3600
        
        summary = f"""
PRANA System Status - {self.location_name}
Last Updated: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')} ({age:.1f} hours ago)

Current Metrics:
- NDT (Heat Stress): {self.current_ndt:.1f}C
- HA-AQI (Air Quality): {self.current_ha_aqi:.0f if self.current_ha_aqi else 'N/A'}
- RDS (Sleep Debt): {self.current_rds:.1f}
- CCRI (Compound Risk): {self.current_ccri:.1f}/100

Status: {'[OK] UPDATE NEEDED' if age > UPDATE_INTERVAL else '[OK] Current'}
"""
        return summary
    
    def add_historical_night_temp(self, night_temp, date):
        """
        Add historical nighttime temperature for RDS tracking
        
        Args:
            night_temp: Nighttime minimum temperature (C)
            date: Date (datetime.date object or string 'YYYY-MM-DD')
        """
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()
        
        self.rds_calculator.add_night_temperature(night_temp, date)
        print(f"Added night temp: {night_temp:.1f}C on {date}")

    def _build_structured_result(self, result, weather, pollutants):
        """Build app-friendly structured fields without removing legacy fields."""
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
                    'value': round(result['ndt'], 1),
                    'unit': 'degC',
                    'level': result['heat_level'],
                },
                'air_quality': {
                    'label': 'Heat-pollution risk',
                    'value': round(result['heat_pollution_risk'], 1) if result['heat_pollution_risk'] is not None else None,
                    'unit': 'score',
                    'base_aqi': round(result['base_aqi'], 1) if result['base_aqi'] is not None else None,
                    'dominant_pollutant': result['air_quality_components'].get('dominant_pollutant'),
                    'pollutant_aqi': result['air_quality_components'].get('pollutant_aqi', {}),
                    'ozone_heat_factor': round(result['ozone_heat_factor'], 2) if result['ozone_heat_factor'] is not None else None,
                    'ozone_heat_adjusted_aqi': (
                        round(result['heat_pollution']['ozone_heat_adjusted_aqi'], 1)
                        if result.get('heat_pollution') and result['heat_pollution'].get('ozone_heat_adjusted_aqi') is not None
                        else None
                    ),
                    'method': result['heat_pollution'].get('method') if result.get('heat_pollution') else None,
                    'confidence': result['heat_pollution'].get('pollution_confidence') if result.get('heat_pollution') else 'LOW',
                },
                'recovery': {
                    'label': 'RDS',
                    'value': round(result['rds'], 1),
                    'unit': 'score',
                    'consecutive_hot_nights': result['consecutive_nights'],
                    'message': result['rds_message'],
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
        """Estimate data confidence from provider coverage."""
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


def demo_prana_system():
    """
    Demonstrate complete PRANA system with YOUR location
    
    This showcases the full temperature calculation pipeline:
    NDT -> HA-AQI -> RDS -> CCRI -> Personalized Alert
    """
    print("\n" + "="*60)
    print("PRANA SYSTEM DEMO")
    print("Asia's First Compound Climate Emergency Platform")
    print("="*60 + "\n")
    
    # Auto-detect user's location
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
    
    # Initialize system
    api_key = OPENWEATHER_API_KEY
    
    prana = PRANASystem(
        api_key=api_key,
        location_name=location_name,
        urban_heat_offset=3.0  # 3C hotter than airport
    )
    
    # Add some historical night temperatures to demonstrate RDS
    print("Adding historical nighttime temperatures for RDS tracking...")
    today = datetime.now().date()
    prana.add_historical_night_temp(34.5, today - timedelta(days=3))
    prana.add_historical_night_temp(35.2, today - timedelta(days=2))
    prana.add_historical_night_temp(36.1, today - timedelta(days=1))
    print()
    
    # Run complete update
    result = prana.update_all(lat, lon)
    
    if result:
        print("\n[OK] PRANA system operational")
        print("\nTo integrate into WhatsApp alerts:")
        print("1. Use result['alert_message'] for personalized notifications")
        print("2. Update every 3 hours via scheduled task")
        print("3. Send via Twilio WhatsApp API to registered users")
    else:
        print("\n[OK] System update failed - check API keys and network connection")


if __name__ == "__main__":
    demo_prana_system()



