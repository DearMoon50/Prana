# PRANA API Contract

This is the first backend contract for the Flutter mobile app.

## Local Run

```powershell
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open the API docs at:

```text
http://127.0.0.1:8000/docs
```

## Health Check

```http
GET /health
```

Returns service status, the active free providers, and whether fallback/reference API keys are configured.

## Current Risk

```http
POST /risk/current
Content-Type: application/json
```

Request:

```json
{
  "lat": 13.0827,
  "lon": 80.2707,
  "location_name": "Chennai, Tamil Nadu, India",
  "urban_heat_offset": 3.0
}
```

Response:

```json
{
  "result": {
    "summary": {
      "title": "PRANA risk is CRITICAL",
      "score": 64.7,
      "risk_level": "CRITICAL",
      "confidence": "HIGH"
    },
    "components": {
      "heat": {
        "label": "NDT",
        "value": 34.6,
        "unit": "degC",
        "level": "VERY HIGH"
      },
      "air_quality": {
        "label": "Heat-pollution risk",
        "value": 210,
        "unit": "score",
        "base_aqi": 166,
        "dominant_pollutant": "PM2.5",
        "pollutant_aqi": {
          "PM2.5": 166,
          "PM10": 90,
          "O3": 80
        },
        "ozone_heat_factor": 1.26,
        "ozone_heat_adjusted_aqi": 101,
        "method": "ozone_specific_heat_adjustment",
        "confidence": "HIGH"
      },
      "recovery": {
        "label": "RDS",
        "value": 66.1,
        "unit": "score",
        "consecutive_hot_nights": 3
      }
    },
    "sources": {
      "weather": "open-meteo",
      "air_quality": ["open-meteo-cams"]
    },
    "timestamp": "2026-06-21T20:30:00",
    "location": "Chennai, Tamil Nadu, India",
    "ndt": 34.6,
    "heat_level": "VERY HIGH",
    "ha_aqi": 210,
    "heat_pollution_risk": 210,
    "base_aqi": 166,
    "oaf": 1.26,
    "ozone_heat_factor": 1.26,
    "rds": 66.1,
    "consecutive_nights": 3,
    "rds_message": "High recovery debt",
    "ccri": 64.7,
    "risk_level": "CRITICAL",
    "alert_message": "..."
  },
  "calculation_log": "..."
}
```

## Flutter App Flow

1. User logs in with phone and email.
2. App asks for location permission and reads GPS coordinates.
3. User adjusts the map pin manually if needed.
4. App calls `POST /risk/current`.
5. Dashboard displays live metrics and stores past results.
6. WhatsApp bot sends warnings and follow-up alerts from backend jobs.

## Backend Data Providers

Current default provider strategy:

- Weather: Open-Meteo Forecast API
- Air quality: Open-Meteo Air Quality API using CAMS model data
- Reference/fallback air quality: OpenAQ when an API key is configured
- Weather fallback: OpenWeatherMap when an API key is configured

OpenWeatherMap is no longer required for local development.

## Mobile App

The Flutter app lives in `mobile_app/`.

Start the backend for phone testing:

```powershell
.\scripts\start_backend.ps1
```

```powershell
cd mobile_app
flutter run
```

For an Android emulator, keep the backend URL as:

```text
http://10.0.2.2:8000
```

For Chrome or Windows desktop builds, use:

```text
http://127.0.0.1:8000
```
