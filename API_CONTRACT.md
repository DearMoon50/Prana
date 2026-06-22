# PRANA API Contract

This is the backend contract for the Flutter mobile app.

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

Returns service status, active free providers, and whether fallback/reference API keys are configured.

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
  "urban_heat_offset": 3.0,
  "sleep_checkin": null
}
```

`sleep_checkin` is optional. When provided it must be a structured object with fields:

```json
{
  "sleep_environment": "too_hot",
  "sleep_quality": "poor",
  "cooling_issue": true,
  "power_issue": false
}
```

Response:

```json
{
  "result": {
    "summary": {
      "title": "PRANA risk is CRITICAL",
      "location": "Chennai, Tamil Nadu, India",
      "score": 64.7,
      "risk_level": "CRITICAL",
      "last_updated": "2026-06-21T20:30:00",
      "confidence": "HIGH"
    },
    "components": {
      "heat": {
        "label": "NDT",
        "description": "estimated_wbgt_plus_urban_offset",
        "value": 34.6,
        "unit": "degC",
        "level": "VERY HIGH",
        "score": 74.0,
        "confidence": "HIGH"
      },
      "air_quality": {
        "label": "Heat-pollution risk",
        "value": 166,
        "unit": "score",
        "base_aqi": 166,
        "dominant_pollutant": "PM2.5",
        "pollutant_aqi": {
          "PM2.5": 166,
          "PM10": 90,
          "O3": 80
        },
        "averaging_windows": {
          "PM2.5": "nowcast_12h",
          "PM10": "instantaneous",
          "O3": "instantaneous"
        },
        "ozone_heat_factor": 1.26,
        "ozone_heat_adjusted_aqi": 100.8,
        "score": 72.0,
        "method": "ozone_specific_heat_adjustment",
        "confidence": "HIGH"
      },
      "recovery": {
        "label": "RDS",
        "description": "outdoor_nighttime_recovery_risk_proxy",
        "value": 66.1,
        "raw_value": 66.1,
        "unit": "score",
        "score": 66.1,
        "consecutive_hot_nights": 3,
        "adjustment": {
          "applied": false,
          "delta": 0.0,
          "reason": "no_checkin",
          "adjusted_rds": 66.1
        },
        "message": "Recovery debt: HIGH (RDS: 66.1 from 3 consecutive hot nights ...)",
        "confidence": "MEDIUM"
      },
      "compound": {
        "label": "CCRI",
        "value": 64.7,
        "unit": "score",
        "heat_score": 74.0,
        "pollution_score": 72.0,
        "recovery_score": 66.1,
        "base_ccri": 53.3,
        "recovery_multiplier": 1.20,
        "confidence": "HIGH"
      }
    },
    "sources": {
      "weather": "open-meteo",
      "air_quality": ["open-meteo-cams"],
      "weather_fields": {
        "wet_bulb_temp": 28.4,
        "shortwave_radiation": 620.0
      }
    },
    "confidence": "HIGH",
    "timestamp": "2026-06-21T20:30:00",
    "location": "Chennai, Tamil Nadu, India",
    "ndt": 34.6,
    "heat_level": "VERY HIGH",
    "ha_aqi": 166,
    "heat_pollution_risk": 166,
    "base_aqi": 166,
    "oaf": 1.26,
    "ozone_heat_factor": 1.26,
    "rds": 66.1,
    "raw_rds": 66.1,
    "consecutive_nights": 3,
    "rds_message": "Recovery debt: HIGH ...",
    "ccri": 64.7,
    "risk_level": "CRITICAL",
    "alert_message": "..."
  },
  "calculation_log": "..."
}
```

### Field notes

- `timestamp` is always an ISO 8601 string (e.g. `"2026-06-21T20:30:00"`).
- `components.heat.description` is always `"estimated_wbgt_plus_urban_offset"`. NDT is a PRANA custom score, not an official WBGT measurement. The urban heat offset is a per-location estimate, not ward/building-level measurement.
- `components.recovery.description` is always `"outdoor_nighttime_recovery_risk_proxy"`. RDS uses outdoor nighttime temperature as a proxy; it is not a measured indoor or personal recovery score.
- `components.air_quality.averaging_windows` describes the averaging method used per pollutant:
  - `"nowcast_12h"` — EPA NowCast weighted average over up to 12 hourly values (used for PM2.5 when history is available).
  - `"instantaneous"` — single reading, not a full official averaging window.
  - `"provider_composite"` — the provider's own composite AQI (Open-Meteo US AQI).
- `components.air_quality.method` is always `"ozone_specific_heat_adjustment"` when air quality data is available. Heat adjusts only the ozone component, not the full AQI.
- `ha_aqi` and `heat_pollution_risk` are legacy fields kept for app compatibility. Both equal `components.air_quality.value`.
- `components.recovery.adjustment` is present when a `sleep_checkin` was submitted. `delta` is the RDS change applied; `raw_value` is the pre-adjustment score.
- All scores labelled PRANA custom (NDT, heat-pollution risk, RDS, CCRI) are risk estimates. They are not official government or medical indices.

## Flutter App Flow

1. User logs in with phone and email.
2. App asks for location permission and reads GPS coordinates.
3. User adjusts the map pin manually if needed.
4. App calls `POST /risk/current`.
5. Dashboard displays live metrics and stores past results in session.
6. WhatsApp bot sends warnings and follow-up alerts from backend jobs.

## Backend Data Providers

- Weather: Open-Meteo Forecast API (no key required)
- Air quality: Open-Meteo Air Quality API — CAMS model data (no key required)
- Reference air quality: OpenAQ v3 when `OPENAQ_API_KEY` is configured
- Weather fallback: OpenWeatherMap when `OPENWEATHER_API_KEY` is configured

## Mobile App

```powershell
.\scripts\start_backend.ps1
```

```powershell
cd mobile_app
flutter run
```

Android emulator backend URL:

```text
http://10.0.2.2:8000
```

Chrome / Windows desktop backend URL:

```text
http://127.0.0.1:8000
```
