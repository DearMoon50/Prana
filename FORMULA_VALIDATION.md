# PRANA Formula Validation

This document tracks the formulas used by PRANA, their status, sources, limitations, and implementation notes.

## Validation Levels

- `STANDARD`: established method or official index calculation.
- `PUBLISHED_APPROXIMATION`: formula from published literature or accepted applied practice, but still approximate in this context.
- `PRANA_CUSTOM`: custom PRANA score or combination.
- `PROTOTYPE_ASSUMPTION`: useful for prototype, but needs stronger validation before public claims.

## NDT: Neighbourhood Danger Temperature

Status: `PRANA_CUSTOM`

Current implementation:

```text
NDT = estimated WBGT + urban heat offset
WBGT = 0.7 * wet_bulb_temp + 0.2 * globe_temp + 0.1 * dry_bulb_temp
```

What is defensible:

- WBGT is an established heat-stress concept.
- PRANA uses weather inputs that reflect temperature, humidity, radiation, and wind.
- Open-Meteo wet-bulb temperature and radiation improve the estimate compared with using air temperature alone.

Limitations:

- Globe temperature is estimated, not measured with a black globe thermometer.
- Urban heat offset is currently user/config supplied, not derived from satellite or land-cover data.
- NDT is not an official public-health index; it is PRANA terminology.

Implementation rule:

- API responses should describe NDT as `estimated_wbgt_plus_urban_offset`.
- Always expose source and confidence.

## Base AQI

Status: `STANDARD` when using official provider AQI; `PUBLISHED_APPROXIMATION` when calculated from pollutant breakpoints.

Current implementation:

- Prefer Open-Meteo `us_aqi` when available.
- Fallback to pollutant breakpoint calculation.

Limitations:

- Official AQI depends on pollutant-specific averaging windows.
- Latest instantaneous pollutant readings should not be presented as fully official AQI unless the provider already applies the AQI method.

Implementation rule:

- Track dominant pollutant and per-pollutant AQI where possible.
- Add data age and averaging-window metadata when available.

## Heat-Pollution Risk

Status: `PRANA_CUSTOM`

Previous prototype:

```text
HA-AQI = base_aqi * OAF
OAF = 1 + 0.04 * max(0, temp_c - 25)
```

Problem:

- Heat mainly affects ozone chemistry; multiplying the full AQI can wrongly amplify PM2.5 or PM10 risk.
- `HA-AQI` sounds like an official AQI, but it is a PRANA risk adjustment.

Updated direction:

```text
ozone_heat_factor = 1 + 0.04 * max(0, temp_c - 25)
ozone_heat_adjusted_aqi = ozone_aqi * ozone_heat_factor
heat_pollution_risk = max(base_aqi, ozone_heat_adjusted_aqi)
```

Implementation rule:

- Keep legacy `ha_aqi` temporarily for app compatibility.
- Add new structured fields:
  - `base_aqi`
  - `dominant_pollutant`
  - `pollutant_aqi`
  - `ozone_heat_factor`
  - `ozone_heat_adjusted_aqi`
  - `heat_pollution_risk`
  - `pollution_confidence`

## RDS: Recovery Debt Score

Status: `PRANA_CUSTOM`

Current implementation:

```text
RFU = 0 if nighttime_temp < 32C
RFU = min(100, ((nighttime_temp - 32) / 10) * 100)
RDS = sum(RFU * 0.8^days_ago)
```

What is defensible:

- Consecutive hot nights and impaired sleep recovery are a real heat-health concern.
- Outdoor nighttime temperature and humidity are reasonable risk signals.

Limitations:

- PRANA does not directly measure indoor temperature.
- Outdoor temperature can understate indoor heat in low-ventilation housing.
- RDS should be described as a recovery-risk estimate unless user check-ins or sensors improve confidence.

Implementation rule:

- Use careful language: "recovery may be impaired", not "your body did not recover".
- Add WhatsApp check-ins only when nighttime heat risk or uncertainty is elevated.
- Use LLM only to extract structured feedback; final RDS calculation remains deterministic.

## CCRI: Compound Climate Risk Index

Status: `PRANA_CUSTOM`

Current implementation:

```text
base_ccri = (heat_score * pollution_score) / 100
rds_multiplier = 1 + (rds / 100) * 0.3
ccri = base_ccri * rds_multiplier
```

What is defensible:

- Compound heat, pollution, and poor recovery can interact in ways that are more serious than any single threat.
- A multiplicative structure is plausible for prototype risk ranking.

Limitations:

- CCRI is not an official government or medical index.
- Thresholds need calibration against observed health outcomes, local heat events, or expert review.

Implementation rule:

- Always label CCRI as a PRANA custom score.
- Return component scores, multipliers, confidence, and limitations.

## Immediate Formula Work

1. Replace full-AQI heat multiplication with ozone-specific adjustment.
2. Return per-pollutant AQI components.
3. Add dominant pollutant and pollution confidence.
4. Move calculation logs behind debug mode.
5. Add unit tests for AQI breakpoints, NDT, RDS, and CCRI.
