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

            if response.status_code == 401:
                print("ERROR: Invalid OpenWeatherMap API key")
                return None
            elif response.status_code == 429:
                print("ERROR: OpenWeatherMap API rate limit exceeded")
                return None

            response.raise_for_status()
            data = response.json()

            return {
                'temp': data['main']['temp'],
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'wind_speed': data['wind']['speed'],
                'timestamp': datetime.fromtimestamp(data['dt']),
                'source': 'openweathermap'
            }
        except requests.exceptions.Timeout:
            print("ERROR: OpenWeatherMap request timed out.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"ERROR: OpenWeatherMap network error - {e}")
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
            'hourly': (
                'temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,'
                'wet_bulb_temperature_2m,shortwave_radiation,direct_radiation,diffuse_radiation'
            ),
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
            for item in data['list'][:hours // 3]:  # 3-hour intervals
                forecasts.append({
                    'temp': item['main']['temp'],
                    'humidity': item['main']['humidity'],
                    'pressure': item['main']['pressure'],
                    'timestamp': datetime.fromtimestamp(item['dt']),
                    'source': 'openweathermap'
                })
            return forecasts
        except Exception as e:
            print(f"WARNING: OpenWeatherMap forecast failed: {e}")
            return None

    def get_air_quality(self, lat, lon, radius_km=25):
        """Get air quality, preferring Open-Meteo model data and falling back to OpenAQ stations."""
        air_quality = self._get_openmeteo_air_quality(lat, lon)
        if air_quality:
            return air_quality

        return self._get_openaq_air_quality(lat, lon, radius_km)

    def _get_openmeteo_air_quality(self, lat, lon):
        """
        Get current air quality from Open-Meteo CAMS model data.

        Fetches the last 12 hourly PM2.5 values in addition to current readings
        so that a NowCast-style weighted average can be computed for PM2.5 AQI.
        """
        params = {
            'latitude': lat,
            'longitude': lon,
            'current': 'us_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone',
            'hourly': 'pm2_5',
            'past_hours': 12,
            'forecast_hours': 1,
            'timezone': 'auto'
        }
        try:
            response = requests.get(OPENMETEO_AIR_QUALITY_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            current = data.get('current', {})
            current_time = current.get('time')

            # Extract last 12 hourly PM2.5 readings for NowCast
            hourly_pm25 = data.get('hourly', {}).get('pm2_5', [])
            # Keep only non-None values from the tail (most recent 12)
            pm25_history = [v for v in hourly_pm25[-12:] if v is not None]

            pollutants = {
                'us_aqi': {
                    'value': current.get('us_aqi'),
                    'unit': 'AQI',
                    'timestamp': current_time,
                    'source': 'open-meteo-cams',
                    'averaging_window': 'provider_composite'
                },
                'pm10': _pollutant(current, 'pm10', 'ug/m3', current_time, 'open-meteo-cams'),
                'pm2.5': _pollutant(current, 'pm2_5', 'ug/m3', current_time, 'open-meteo-cams'),
                'co': _pollutant(current, 'carbon_monoxide', 'ug/m3', current_time, 'open-meteo-cams'),
                'no2': _pollutant(current, 'nitrogen_dioxide', 'ug/m3', current_time, 'open-meteo-cams'),
                'so2': _pollutant(current, 'sulphur_dioxide', 'ug/m3', current_time, 'open-meteo-cams'),
                'o3': _pollutant(current, 'ozone', 'ug/m3', current_time, 'open-meteo-cams'),
            }

            # Attach PM2.5 history for NowCast use in AQI calculation
            if pm25_history and 'pm2.5' in pollutants:
                pollutants['pm2.5']['history_12h'] = pm25_history

            pollutants = {k: v for k, v in pollutants.items() if v.get('value') is not None}
            if pollutants:
                print(f"  [OK] Open-Meteo air quality: {', '.join(pollutants.keys())}")
                return pollutants

            return None
        except Exception as e:
            print(f"WARNING: Open-Meteo air quality failed: {e}")
            return None

    def _get_openaq_air_quality(self, lat, lon, radius_km=25):
        """Get air quality data from OpenAQ v3 API."""
        if not self.openaq_api_key:
            print("WARNING: OpenAQ API key not set - skipping air quality data")
            return None

        headers = {'X-API-Key': self.openaq_api_key}

        try:
            params = {
                'coordinates': f"{lat},{lon}",
                'radius': radius_km * 1000,
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

            location = locations_data['results'][0]
            location_id = location['id']
            location_name = location.get('name', 'Unknown')
            print(f"  Found station: {location_name} (ID: {location_id})")

            location_detail_url = f"https://api.openaq.org/v3/locations/{location_id}"
            loc_response = requests.get(location_detail_url, headers=headers, timeout=10)
            loc_response.raise_for_status()
            loc_data = loc_response.json()

            if not loc_data.get('results'):
                return None

            sensors = loc_data['results'][0].get('sensors', [])
            if not sensors:
                return None

            pollutants = {}

            for sensor in sensors:
                sensor_id = sensor['id']
                param_name = sensor['parameter']['name'].lower()

                sensor_measurements_url = f"https://api.openaq.org/v3/sensors/{sensor_id}/measurements"
                s_params = {'limit': 1, 'order_by': 'datetime', 'sort_order': 'desc'}

                try:
                    sensor_response = requests.get(
                        sensor_measurements_url, headers=headers, params=s_params, timeout=5
                    )
                    if sensor_response.status_code != 200:
                        continue

                    sensor_data = sensor_response.json()
                    if sensor_data.get('results'):
                        measurement = sensor_data['results'][0]
                        timestamp = measurement.get('datetime', {})
                        if isinstance(timestamp, dict):
                            timestamp = timestamp.get('utc', 'Unknown')

                        pollutants[param_name] = {
                            'value': measurement['value'],
                            'unit': _normalize_unit(sensor['parameter']['units']),
                            'timestamp': timestamp,
                            'source': 'openaq',
                            'averaging_window': 'instantaneous'
                        }
                except Exception:
                    continue

            if pollutants:
                print(f"  [OK] OpenAQ measurements: {', '.join(pollutants.keys())}")
                return pollutants

            return None

        except requests.exceptions.Timeout:
            print("WARNING: OpenAQ request timed out")
            return None
        except requests.exceptions.RequestException as e:
            print(f"WARNING: OpenAQ error: {e}")
            return None

    def calculate_aqi_from_pollutants(self, pollutants):
        result = self.calculate_pollutant_aqi_components(pollutants)
        return result['base_aqi']

    def calculate_pollutant_aqi_components(self, pollutants, debug=False):
        """
        Calculate per-pollutant AQI components and the dominant base AQI.

        For PM2.5, uses EPA NowCast weighted average when 12-hour history is
        available, otherwise falls back to instantaneous concentration.

        Returns dict with base_aqi, dominant_pollutant, pollutant_aqi,
        averaging_windows, and source.
        """
        if not pollutants:
            return {
                'base_aqi': None,
                'dominant_pollutant': None,
                'pollutant_aqi': {},
                'averaging_windows': {},
                'source': None
            }

        if 'us_aqi' in pollutants and pollutants['us_aqi'].get('value') is not None:
            provider_aqi = pollutants['us_aqi']['value']
            pollutant_aqi, averaging_windows = self._calculate_pollutant_aqi_values(
                pollutants, debug=debug
            )
            dominant_pollutant = None
            if pollutant_aqi:
                dominant_pollutant, _ = max(pollutant_aqi.items(), key=lambda x: x[1])
            if debug:
                print(f"  -> Overall AQI: {provider_aqi:.0f} (from Open-Meteo US AQI)")
            return {
                'base_aqi': provider_aqi,
                'dominant_pollutant': dominant_pollutant or 'provider_aqi',
                'pollutant_aqi': pollutant_aqi,
                'averaging_windows': averaging_windows,
                'source': pollutants['us_aqi'].get('source', 'provider')
            }

        pollutant_aqi, averaging_windows = self._calculate_pollutant_aqi_values(
            pollutants, debug=debug
        )
        if not pollutant_aqi:
            return {
                'base_aqi': None,
                'dominant_pollutant': None,
                'pollutant_aqi': {},
                'averaging_windows': {},
                'source': None
            }

        dominant_pollutant, base_aqi = max(pollutant_aqi.items(), key=lambda x: x[1])
        if debug:
            print(f"  -> Overall AQI: {base_aqi:.0f} (limited by {dominant_pollutant})")

        return {
            'base_aqi': base_aqi,
            'dominant_pollutant': dominant_pollutant,
            'pollutant_aqi': pollutant_aqi,
            'averaging_windows': averaging_windows,
            'source': 'calculated_breakpoints'
        }

    def _calculate_pollutant_aqi_values(self, pollutants, debug=False):
        """
        Return (pollutant_aqi dict, averaging_windows dict).

        PM2.5 uses EPA NowCast (12-hour weighted average) when history is
        available. All other pollutants use instantaneous concentration with
        EPA breakpoints and are labelled accordingly.
        """
        pollutant_aqi = {}
        averaging_windows = {}

        if debug:
            print("  Calculating AQI from pollutants:")

        # PM2.5 — NowCast when history available, instantaneous fallback
        pm25_key = 'pm25' if 'pm25' in pollutants else ('pm2.5' if 'pm2.5' in pollutants else None)
        if pm25_key:
            entry = pollutants[pm25_key]
            unit = _normalize_unit(entry['unit'])
            if unit == 'ug/m3':
                history = entry.get('history_12h')
                if history and len(history) >= 3:
                    pm25_conc = _pm25_nowcast(history)
                    window = 'nowcast_12h'
                else:
                    pm25_conc = entry['value']
                    window = 'instantaneous'
                pm25_aqi = self._calculate_pm25_aqi(pm25_conc)
                pollutant_aqi['PM2.5'] = pm25_aqi
                averaging_windows['PM2.5'] = window
                if debug:
                    print(f"    PM2.5: {pm25_conc:.1f} ug/m3 [{window}] -> AQI {pm25_aqi:.0f}")

        # PM10 — instantaneous
        if 'pm10' in pollutants:
            entry = pollutants['pm10']
            unit = _normalize_unit(entry['unit'])
            if unit == 'ug/m3':
                pm10_aqi = self._calculate_pm10_aqi(entry['value'])
                pollutant_aqi['PM10'] = pm10_aqi
                averaging_windows['PM10'] = 'instantaneous'
                if debug:
                    print(f"    PM10: {entry['value']} ug/m3 -> AQI {pm10_aqi:.0f}")

        # Ozone
        if 'o3' in pollutants:
            entry = pollutants['o3']
            o3_value = entry['value']
            unit = _normalize_unit(entry['unit'])
            o3_ppm = o3_value / 2000 if unit == 'ug/m3' else o3_value
            o3_aqi = self._calculate_o3_aqi(o3_ppm)
            pollutant_aqi['O3'] = o3_aqi
            averaging_windows['O3'] = 'instantaneous'
            if debug:
                print(f"    O3: {o3_value} {unit} ({o3_ppm:.3f} ppm) -> AQI {o3_aqi:.0f}")

        # CO
        if 'co' in pollutants:
            entry = pollutants['co']
            co_value = entry['value']
            unit = _normalize_unit(entry['unit'])
            if unit == 'ug/m3':
                co_ppm = co_value / 1150
            elif unit == 'mg/m3':
                co_ppm = (co_value * 1000) / 1150
            elif unit == 'ppm':
                co_ppm = co_value
            else:
                co_ppm = co_value / 1150 if co_value > 100 else co_value
            co_aqi = self._calculate_co_aqi(co_ppm)
            pollutant_aqi['CO'] = co_aqi
            averaging_windows['CO'] = 'instantaneous'
            if debug:
                print(f"    CO: {co_value} {unit} ({co_ppm:.2f} ppm) -> AQI {co_aqi:.0f}")

        # NO2
        if 'no2' in pollutants:
            entry = pollutants['no2']
            no2_value = entry['value']
            unit = _normalize_unit(entry['unit'])
            no2_ppb = no2_value / 1.88 if unit == 'ug/m3' else no2_value
            no2_aqi = self._calculate_no2_aqi(no2_ppb)
            pollutant_aqi['NO2'] = no2_aqi
            averaging_windows['NO2'] = 'instantaneous'
            if debug:
                print(f"    NO2: {no2_value} {unit} ({no2_ppb:.1f} ppb) -> AQI {no2_aqi:.0f}")

        return pollutant_aqi, averaging_windows

    def _calculate_pm25_aqi(self, pm25):
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
        for bp_lo, bp_hi, aqi_lo, aqi_hi in breakpoints:
            if bp_lo <= concentration <= bp_hi:
                return ((aqi_hi - aqi_lo) / (bp_hi - bp_lo)) * (concentration - bp_lo) + aqi_lo
        return 500


# ---------------------------------------------------------------------------
# EPA NowCast for PM2.5
# ---------------------------------------------------------------------------

def _pm25_nowcast(hourly_values):
    """
    Compute EPA NowCast weighted average for PM2.5.

    hourly_values: list of up to 12 hourly concentrations, most recent last.
    Weight for each hour i (0 = most recent): w^i where w = max(0.5, min_c/max_c).
    Returns weighted average concentration.
    """
    values = [v for v in hourly_values if v is not None]
    if not values:
        return 0.0
    min_c = min(values)
    max_c = max(values)
    w = max(0.5, min_c / max_c) if max_c > 0 else 0.5
    # Most recent value is last in the list
    weighted_sum = 0.0
    weight_sum = 0.0
    for i, val in enumerate(reversed(values)):
        weight = w ** i
        weighted_sum += val * weight
        weight_sum += weight
    return weighted_sum / weight_sum if weight_sum > 0 else values[-1]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

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
        'source': source,
        'averaging_window': 'instantaneous'
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
