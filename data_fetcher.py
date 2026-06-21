"""Fetch climate and air quality data from public APIs"""
import requests
import numpy as np
from datetime import datetime, timedelta
from config import *

class DataFetcher:
    def __init__(self, api_key, openaq_api_key=None):
        self.api_key = api_key
        self.openaq_api_key = openaq_api_key or OPENAQ_API_KEY
        
    def get_current_weather(self, lat, lon):
        """Get current weather data, preferring Open-Meteo and falling back to OpenWeatherMap."""
        weather = self._get_openmeteo_current_weather(lat, lon)
        if weather:
            return weather

        if not self.api_key:
            print("WARNING: Open-Meteo weather failed and OPENWEATHER_API_KEY is not set")
            return None

        return self._get_openweather_current_weather(lat, lon)

    def _get_openmeteo_current_weather(self, lat, lon):
        """Get current weather from Open-Meteo without an API key."""
        params = {
            'latitude': lat,
            'longitude': lon,
            'current': 'temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m',
            'hourly': 'wet_bulb_temperature_2m,shortwave_radiation,direct_radiation,diffuse_radiation',
            'forecast_hours': 1,
            'timezone': 'auto',
            'wind_speed_unit': 'ms'
        }
        try:
            response = requests.get(OPENMETEO_FORECAST_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            current = data.get('current', {})
            hourly = data.get('hourly', {})

            return {
                'temp': current['temperature_2m'],
                'humidity': current['relative_humidity_2m'],
                'pressure': current.get('surface_pressure', 1013.25),
                'wind_speed': current.get('wind_speed_10m', 0.5),
                'wet_bulb_temp': _first_hourly_value(hourly, 'wet_bulb_temperature_2m'),
                'shortwave_radiation': _first_hourly_value(hourly, 'shortwave_radiation'),
                'direct_radiation': _first_hourly_value(hourly, 'direct_radiation'),
                'diffuse_radiation': _first_hourly_value(hourly, 'diffuse_radiation'),
                'timestamp': _parse_openmeteo_time(current.get('time')),
                'source': 'open-meteo'
            }
        except Exception as e:
            print(f"WARNING: Open-Meteo weather failed: {e}")
            return None

    def _get_openweather_current_weather(self, lat, lon):
        """Get current weather data from OpenWeatherMap"""
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'units': 'metric'
        }
        try:
            response = requests.get(OPENWEATHER_URL, params=params, timeout=10)
            
            # Check for specific error codes
            if response.status_code == 401:
                print(f"ERROR: Invalid API key")
                print(f"   Your key: {self.api_key[:20]}...")
                print(f"\n   Please check:")
                print(f"   1. Go to https://home.openweathermap.org/api_keys")
                print(f"   2. Make sure your API key is activated (takes ~10 minutes)")
                print(f"   3. Copy the CORRECT key to .env file")
                return None
            elif response.status_code == 429:
                print(f"ERROR: API rate limit exceeded")
                print(f"   Wait a few minutes and try again")
                return None
            
            response.raise_for_status()
            data = response.json()
            
            return {
                'temp': data['main']['temp'],
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'wind_speed': data['wind']['speed'],
                'timestamp': datetime.fromtimestamp(data['dt'])
            }
        except requests.exceptions.Timeout:
            print("ERROR: Request timed out. Check your internet connection.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Network error - {e}")
            return None
        except Exception as e:
            print(f"ERROR fetching weather: {e}")
            return None
    
    def get_forecast(self, lat, lon, hours=24):
        """Get weather forecast, preferring Open-Meteo and falling back to OpenWeatherMap."""
        forecast = self._get_openmeteo_forecast(lat, lon, hours)
        if forecast:
            return forecast

        if not self.api_key:
            print("WARNING: Open-Meteo forecast failed and OPENWEATHER_API_KEY is not set")
            return None

        return self._get_openweather_forecast(lat, lon, hours)

    def _get_openmeteo_forecast(self, lat, lon, hours=24):
        """Get hourly forecast from Open-Meteo without an API key."""
        params = {
            'latitude': lat,
            'longitude': lon,
            'hourly': 'temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,wet_bulb_temperature_2m,shortwave_radiation,direct_radiation,diffuse_radiation',
            'forecast_hours': hours,
            'timezone': 'auto',
            'wind_speed_unit': 'ms'
        }
        try:
            response = requests.get(OPENMETEO_FORECAST_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            hourly = data.get('hourly', {})
            times = hourly.get('time', [])
            forecasts = []

            for i, time_value in enumerate(times[:hours]):
                forecasts.append({
                    'temp': hourly['temperature_2m'][i],
                    'humidity': hourly['relative_humidity_2m'][i],
                    'pressure': hourly.get('surface_pressure', [1013.25] * len(times))[i],
                    'wind_speed': hourly.get('wind_speed_10m', [0.5] * len(times))[i],
                    'wet_bulb_temp': hourly.get('wet_bulb_temperature_2m', [None] * len(times))[i],
                    'shortwave_radiation': hourly.get('shortwave_radiation', [None] * len(times))[i],
                    'direct_radiation': hourly.get('direct_radiation', [None] * len(times))[i],
                    'diffuse_radiation': hourly.get('diffuse_radiation', [None] * len(times))[i],
                    'timestamp': _parse_openmeteo_time(time_value),
                    'source': 'open-meteo'
                })

            return forecasts
        except Exception as e:
            print(f"WARNING: Open-Meteo forecast failed: {e}")
            return None

    def _get_openweather_forecast(self, lat, lon, hours=24):
        """Get weather forecast from OpenWeatherMap"""
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'units': 'metric'
        }
        try:
            response = requests.get(OPENWEATHER_FORECAST_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            forecasts = []
            for item in data['list'][:hours//3]:  # 3-hour intervals
                forecasts.append({
                    'temp': item['main']['temp'],
                    'humidity': item['main']['humidity'],
                    'pressure': item['main']['pressure'],
                    'timestamp': datetime.fromtimestamp(item['dt'])
                })
            return forecasts
        except Exception as e:
            print(f"Error fetching forecast: {e}")
            return None
    
    def get_air_quality(self, lat, lon, radius_km=25):
        """Get air quality, preferring Open-Meteo model data and falling back to OpenAQ stations."""
        air_quality = self._get_openmeteo_air_quality(lat, lon)
        if air_quality:
            return air_quality

        return self._get_openaq_air_quality(lat, lon, radius_km)

    def _get_openmeteo_air_quality(self, lat, lon):
        """Get current air quality from Open-Meteo CAMS model data."""
        params = {
            'latitude': lat,
            'longitude': lon,
            'current': 'us_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone',
            'hourly': 'us_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone',
            'forecast_hours': 24,
            'timezone': 'auto'
        }
        try:
            response = requests.get(OPENMETEO_AIR_QUALITY_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            current = data.get('current', {})
            current_time = current.get('time')

            pollutants = {
                'us_aqi': {
                    'value': current.get('us_aqi'),
                    'unit': 'AQI',
                    'timestamp': current_time,
                    'source': 'open-meteo-cams'
                },
                'pm10': _pollutant(current, 'pm10', 'ug/m3', current_time, 'open-meteo-cams'),
                'pm2.5': _pollutant(current, 'pm2_5', 'ug/m3', current_time, 'open-meteo-cams'),
                'co': _pollutant(current, 'carbon_monoxide', 'ug/m3', current_time, 'open-meteo-cams'),
                'no2': _pollutant(current, 'nitrogen_dioxide', 'ug/m3', current_time, 'open-meteo-cams'),
                'so2': _pollutant(current, 'sulphur_dioxide', 'ug/m3', current_time, 'open-meteo-cams'),
                'o3': _pollutant(current, 'ozone', 'ug/m3', current_time, 'open-meteo-cams'),
            }

            pollutants = {key: value for key, value in pollutants.items() if value.get('value') is not None}
            if pollutants:
                print(f"  [OK] Open-Meteo air quality: {', '.join(pollutants.keys())}")
                return pollutants

            return None
        except Exception as e:
            print(f"WARNING: Open-Meteo air quality failed: {e}")
            return None

    def _get_openaq_air_quality(self, lat, lon, radius_km=25):
        """
        Get air quality data from OpenAQ v3 API
        
        OpenAQ v3 two-step process:
        1. Find locations near coordinates -> get location IDs
        2. Get sensors for location -> get sensor IDs  
        3. Fetch measurements from each sensor
        
        Note: OpenAQ v2 was retired January 31, 2025
        v3 requires API key - get free key from https://openaq.org
        """
        if not self.openaq_api_key:
            print("WARNING: OpenAQ API key not set - skipping air quality data")
            print("         Get free key from: https://openaq.org")
            print("         Add to .env: OPENAQ_API_KEY=your_key")
            return None
        
        headers = {'X-API-Key': self.openaq_api_key}
        
        try:
            # Step 1: Find nearby locations
            print(f"  Searching for air quality monitors within {radius_km}km...")
            params = {
                'coordinates': f"{lat},{lon}",
                'radius': radius_km * 1000,  # meters
                'limit': 5
            }
            
            response = requests.get(OPENAQ_URL, headers=headers, params=params, timeout=10)
            
            if response.status_code == 401:
                print("WARNING: OpenAQ API key invalid")
                return None
            elif response.status_code == 410:
                print("WARNING: OpenAQ v2 endpoint retired - using v3")
                return None
            
            response.raise_for_status()
            locations_data = response.json()
            
            if not locations_data.get('results'):
                print(f"  No air quality monitoring stations within {radius_km}km")
                return None
            
            # Step 2: Get sensors from nearest location
            location = locations_data['results'][0]
            location_id = location['id']
            location_name = location.get('name', 'Unknown')
            
            print(f"  Found station: {location_name} (ID: {location_id})")
            
            # Get full location details including sensors
            location_detail_url = f"https://api.openaq.org/v3/locations/{location_id}"
            loc_response = requests.get(location_detail_url, headers=headers, timeout=10)
            loc_response.raise_for_status()
            loc_data = loc_response.json()
            
            if not loc_data.get('results'):
                print(f"  Could not get sensors for location {location_id}")
                return None
            
            sensors = loc_data['results'][0].get('sensors', [])
            
            if not sensors:
                print(f"  No sensors found at this location")
                return None
            
            # Print available sensors
            sensor_list = [(s['id'], s['parameter']['name']) for s in sensors]
            print(f"  Available sensors: {', '.join([f'{name}' for _, name in sensor_list])}")
            
            # Step 3: Fetch latest measurements from each sensor
            # Note: /latest endpoint may not exist, use /measurements with limit=1
            pollutants = {}
            
            print(f"  Fetching measurements from {len(sensors)} sensors...")
            
            for sensor in sensors:
                sensor_id = sensor['id']
                param_name = sensor['parameter']['name'].lower()
                
                # Get most recent measurement for this sensor
                sensor_measurements_url = f"https://api.openaq.org/v3/sensors/{sensor_id}/measurements"
                params = {
                    'limit': 1,
                    'order_by': 'datetime',
                    'sort_order': 'desc'
                }
                
                try:
                    sensor_response = requests.get(sensor_measurements_url, headers=headers, params=params, timeout=5)
                    
                    if sensor_response.status_code != 200:
                        print(f"    {param_name}: HTTP {sensor_response.status_code}")
                        continue
                    
                    sensor_data = sensor_response.json()
                    
                    if sensor_data.get('results') and len(sensor_data['results']) > 0:
                        measurement = sensor_data['results'][0]
                        # Handle datetime structure (could be dict or string)
                        timestamp = measurement.get('datetime', {})
                        if isinstance(timestamp, dict):
                            timestamp = timestamp.get('utc', 'Unknown')
                        
                        value = measurement['value']
                        unit = _normalize_unit(sensor['parameter']['units'])
                        
                        pollutants[param_name] = {
                            'value': value,
                            'unit': unit,
                            'timestamp': timestamp,
                            'source': 'openaq'
                        }
                        print(f"    {param_name}: {value} {unit} (raw from API)")
                    else:
                        print(f"    {param_name}: Empty results")
                
                except Exception as e:
                    print(f"    {param_name}: Error - {str(e)[:50]}")
                    continue
            
            if pollutants:
                print(f"  [OK] Got measurements: {', '.join(pollutants.keys())}")
                return pollutants
            else:
                print(f"  No valid measurements retrieved")
                return None
            
        except requests.exceptions.Timeout:
            print("WARNING: OpenAQ request timed out")
            return None
        except requests.exceptions.RequestException as e:
            print(f"WARNING: OpenAQ error: {e}")
            return None
        except Exception as e:
            print(f"WARNING: Error fetching air quality: {e}")
            return None
    
    def calculate_aqi_from_pollutants(self, pollutants):
        """
        Calculate AQI from pollutant concentrations (US EPA standard)
        Uses proper EPA breakpoint tables per pollutant
        """
        result = self.calculate_pollutant_aqi_components(pollutants, debug=True)
        return result['base_aqi']

    def calculate_pollutant_aqi_components(self, pollutants, debug=False):
        """
        Calculate per-pollutant AQI components and the dominant base AQI.

        Returns:
            Dict with base_aqi, dominant_pollutant, pollutant_aqi, and source.
        """
        if not pollutants:
            return {
                'base_aqi': None,
                'dominant_pollutant': None,
                'pollutant_aqi': {},
                'source': None
            }

        if 'us_aqi' in pollutants and pollutants['us_aqi'].get('value') is not None:
            provider_aqi = pollutants['us_aqi']['value']
            pollutant_aqi = self._calculate_pollutant_aqi_values(pollutants, debug=debug)
            dominant_pollutant = None
            if pollutant_aqi:
                dominant_pollutant, _ = max(pollutant_aqi.items(), key=lambda item: item[1])
            if debug:
                print(f"  -> Overall AQI: {provider_aqi:.0f} (from Open-Meteo US AQI)")
            return {
                'base_aqi': provider_aqi,
                'dominant_pollutant': dominant_pollutant or 'provider_aqi',
                'pollutant_aqi': pollutant_aqi,
                'source': pollutants['us_aqi'].get('source', 'provider')
            }

        pollutant_aqi = self._calculate_pollutant_aqi_values(pollutants, debug=debug)
        if not pollutant_aqi:
            return {
                'base_aqi': None,
                'dominant_pollutant': None,
                'pollutant_aqi': {},
                'source': None
            }

        dominant_pollutant, base_aqi = max(pollutant_aqi.items(), key=lambda item: item[1])
        if debug:
            print(f"  -> Overall AQI: {base_aqi:.0f} (limited by {dominant_pollutant})")

        return {
            'base_aqi': base_aqi,
            'dominant_pollutant': dominant_pollutant,
            'pollutant_aqi': pollutant_aqi,
            'source': 'calculated_breakpoints'
        }

    def _calculate_pollutant_aqi_values(self, pollutants, debug=False):
        if not pollutants:
            return {}
        
        pollutant_aqi = {}
        
        if debug:
            print(f"  Calculating AQI from pollutants:")
        
        # PM2.5 (ug/m3)
        if 'pm25' in pollutants or 'pm2.5' in pollutants:
            pm25_key = 'pm25' if 'pm25' in pollutants else 'pm2.5'
            pm25 = pollutants[pm25_key]['value']
            unit = _normalize_unit(pollutants[pm25_key]['unit'])
            
            if unit == 'ug/m3':
                pm25_aqi = self._calculate_pm25_aqi(pm25)
                pollutant_aqi['PM2.5'] = pm25_aqi
                if debug:
                    print(f"    PM2.5: {pm25} ug/m3 -> AQI {pm25_aqi:.0f}")
        
        # PM10 (ug/m3)
        if 'pm10' in pollutants:
            pm10 = pollutants['pm10']['value']
            unit = _normalize_unit(pollutants['pm10']['unit'])
            
            if unit == 'ug/m3':
                pm10_aqi = self._calculate_pm10_aqi(pm10)
                pollutant_aqi['PM10'] = pm10_aqi
                if debug:
                    print(f"    PM10: {pm10} ug/m3 -> AQI {pm10_aqi:.0f}")
        
        # Ozone (convert to ppm if in ug/m3)
        if 'o3' in pollutants:
            o3_value = pollutants['o3']['value']
            unit = _normalize_unit(pollutants['o3']['unit'])
            
            # Convert ug/m3 to ppm if needed (at 25C, 1 atm)
            if unit == 'ug/m3':
                # O3: 1 ppm = 2000 ug/m3 (approx at 25C)
                o3_ppm = o3_value / 2000
            elif unit == 'ppm':
                o3_ppm = o3_value
            else:
                o3_ppm = o3_value / 2000  # Default assume ug/m3
            
            o3_aqi = self._calculate_o3_aqi(o3_ppm)
            pollutant_aqi['O3'] = o3_aqi
            if debug:
                print(f"    O3: {o3_value} {unit} ({o3_ppm:.3f} ppm) -> AQI {o3_aqi:.0f}")
        
        # CO (convert from ug/m3 or mg/m3 to ppm)
        if 'co' in pollutants:
            co_value = pollutants['co']['value']
            unit = _normalize_unit(pollutants['co']['unit'])
            
            # CO: 1 ppm = 1150 ug/m3 (approx at 25C)
            if unit == 'ug/m3':
                co_ppm = co_value / 1150
            elif unit == 'mg/m3':
                co_ppm = (co_value * 1000) / 1150
            elif unit == 'ppm':
                co_ppm = co_value
            else:
                # If unit unclear, check magnitude
                if co_value > 100:  # Likely ug/m3
                    co_ppm = co_value / 1150
                else:
                    co_ppm = co_value
            
            co_aqi = self._calculate_co_aqi(co_ppm)
            pollutant_aqi['CO'] = co_aqi
            if debug:
                print(f"    CO: {co_value} {unit} ({co_ppm:.2f} ppm) -> AQI {co_aqi:.0f}")
        
        # NO2 (ppb to AQI)
        if 'no2' in pollutants:
            no2_value = pollutants['no2']['value']
            unit = _normalize_unit(pollutants['no2']['unit'])
            
            # NO2: 1 ppb = 1.88 ug/m3 (approx at 25C)
            if unit == 'ug/m3':
                no2_ppb = no2_value / 1.88
            elif unit == 'ppb':
                no2_ppb = no2_value
            else:
                no2_ppb = no2_value / 1.88  # Default assume ug/m3
            
            no2_aqi = self._calculate_no2_aqi(no2_ppb)
            pollutant_aqi['NO2'] = no2_aqi
            if debug:
                print(f"    NO2: {no2_value} {unit} ({no2_ppb:.1f} ppb) -> AQI {no2_aqi:.0f}")

        return pollutant_aqi
    
    def _calculate_pm25_aqi(self, pm25):
        """Calculate AQI for PM2.5"""
        breakpoints = [
            (0, 9.0, 0, 50),
            (9.1, 35.4, 51, 100),
            (35.5, 55.4, 101, 150),
            (55.5, 125.4, 151, 200),
            (125.5, 225.4, 201, 300),
            (225.5, 325.4, 301, 500)
        ]
        return self._calculate_aqi(pm25, breakpoints)
    
    def _calculate_pm10_aqi(self, pm10):
        """Calculate AQI for PM10"""
        breakpoints = [
            (0, 54, 0, 50),
            (55, 154, 51, 100),
            (155, 254, 101, 150),
            (255, 354, 151, 200),
            (355, 424, 201, 300),
            (425, 604, 301, 500)
        ]
        return self._calculate_aqi(pm10, breakpoints)
    
    def _calculate_o3_aqi(self, o3_ppm):
        """Calculate AQI for Ozone (8-hour average, ppm)"""
        o3_ppb = o3_ppm * 1000
        breakpoints = [
            (0, 54, 0, 50),
            (55, 70, 51, 100),
            (71, 85, 101, 150),
            (86, 105, 151, 200),
            (106, 200, 201, 300)
        ]
        return self._calculate_aqi(o3_ppb, breakpoints)
    
    def _calculate_co_aqi(self, co_ppm):
        """Calculate AQI for CO (8-hour average, ppm)"""
        breakpoints = [
            (0.0, 4.4, 0, 50),
            (4.5, 9.4, 51, 100),
            (9.5, 12.4, 101, 150),
            (12.5, 15.4, 151, 200),
            (15.5, 30.4, 201, 300),
            (30.5, 50.4, 301, 500)
        ]
        return self._calculate_aqi(co_ppm, breakpoints)
    
    def _calculate_no2_aqi(self, no2_ppb):
        """Calculate AQI for NO2 (1-hour average, ppb)"""
        breakpoints = [
            (0, 53, 0, 50),
            (54, 100, 51, 100),
            (101, 360, 101, 150),
            (361, 649, 151, 200),
            (650, 1249, 201, 300),
            (1250, 2049, 301, 500)
        ]
        return self._calculate_aqi(no2_ppb, breakpoints)
    
    def _calculate_aqi(self, concentration, breakpoints):
        """Generic AQI calculation from breakpoints"""
        for bp_lo, bp_hi, aqi_lo, aqi_hi in breakpoints:
            if bp_lo <= concentration <= bp_hi:
                return ((aqi_hi - aqi_lo) / (bp_hi - bp_lo)) * (concentration - bp_lo) + aqi_lo
        return 500  # Max AQI if exceeds all breakpoints


def _first_hourly_value(hourly, key):
    values = hourly.get(key) or []
    return values[0] if values else None


def _parse_openmeteo_time(value):
    if not value:
        return datetime.now()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now()


def _pollutant(current, key, unit, timestamp, source):
    return {
        'value': current.get(key),
        'unit': _normalize_unit(unit),
        'timestamp': timestamp,
        'source': source
    }


def _normalize_unit(unit):
    if unit is None:
        return ''

    value = str(unit)
    lower_value = value.lower()
    if 'g/m' in lower_value and 'm' in lower_value:
        if lower_value.startswith('m'):
            return 'mg/m3'
        return 'ug/m3'
    return lower_value

