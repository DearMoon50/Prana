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

## Urban Heat Island Offset Lookup

Status: `PUBLISHED_APPROXIMATION` (values from published UHI studies; not from real-time satellite ingestion)

Data source: `uhi_lookup.py` — static dictionary of city/district → estimated UHI offset (degC).

Last updated: 2026-06-22

Demo cities covered:

| City | Country | Default offset (°C) | Districts |
|------|---------|---------------------|-----------|
| Ho Chi Minh City | Vietnam | 3.5 | 22 |
| Chennai | India | 3.0 | 18 |
| Dhaka | Bangladesh | 4.0 | 15 |
| Karachi | Pakistan | 3.0 | 15 |
| Manila | Philippines | 3.5 | 31 |
| Jakarta | Indonesia | 4.0 | 18 |

Behaviour:

- `PRANASystem.__init__` calls `lookup_uhi_offset(location_name)` when `urban_heat_offset` is not explicitly provided.
- Function matches city name then district name (case-insensitive substring).
- Falls back to manual default (3.0 °C) if no match.

Implementation rule:

- Document this as a prototype convenience, not real-time satellite measurement.
- The district-level values are coarse estimates; refine with localised LST analysis before production.

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

Updated direction (v2):

```text
ozone_heat_factor = 1 + 0.04 * max(0, temp_c - 25)
ozone_heat_adjusted_aqi = ozone_aqi * ozone_heat_factor
heat_driven_increment = (ozone_heat_adjusted_aqi - ozone_aqi) * OAF_BLEND_WEIGHT
heat_pollution_risk = base_aqi + heat_driven_increment
```

`OAF_BLEND_WEIGHT = 0.5` in config.py (2026-06-22). The heat-driven ozone increment is blended at 50 % onto base AQI, so every day with nonzero ozone and nonzero temperature excess gets some heat coupling.

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
- Onboarding-derived indoor offset (AC: -3°C, tin roof: +2°C, top floor: +1.5°C) is a `PROTOTYPE_ASSUMPTION` — not empirically validated.

Implementation rule:

- Use careful language: "recovery may be impaired", not "your body did not recover".
- Add WhatsApp check-ins only when nighttime heat risk or uncertainty is elevated.
- Use LLM only to extract structured feedback; final RDS calculation remains deterministic.
- Onboarding adjustment is fully optional: `RDSCalculator(onboarding_data=None)` computes exactly as before.

## RDS Onboarding Adjustment (Indoor Proxy)

Status: `PROTOTYPE_ASSUMPTION`

Added 2026-06-22.

Formula:

```text
indoor_offset = (AC ? -3.0 : 0.0) + (roof_material == 'tin' ? +2.0 : 0.0) + (floor_level == 'top' ? +1.5 : 0.0)
effective_temp = outdoor_night_temp + indoor_offset
```

The offset is applied before the existing 32 °C RFU threshold.

| Input | Value | Effect |
|-------|-------|--------|
| `ac: true` | −3.0 °C | Mechanical cooling lowers effective indoor temp |
| `roof_material: 'tin'` | +2.0 °C | Tin roof heats up faster than concrete |
| `floor_level: 'top'` | +1.5 °C | Top floor receives more roof-transmitted heat |

Constants in `config.py`:
- `RDS_ONBOARDING_AC_OFFSET = -3.0`
- `RDS_ONBOARDING_TIN_ROOF_OFFSET = 2.0`
- `RDS_ONBOARDING_TOP_FLOOR_OFFSET = 1.5`

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

CCRI RDS weighting (current constant `0.3`):

See `scripts/ccri_rds_sensitivity.py` for the full sensitivity table.
Key findings (2026-06-22):

| Metric | Value |
|--------|-------|
| Average RDS spread | 8.1 CCRI points |
| Max RDS spread | 22.7 CCRI points |
| Min RDS spread | 1.3 CCRI points |
| Tier changes (RDS 0→100) | 7/25 = 28% of scenarios |

The 0.3 constant caps RDS influence between 1.0× and 1.3×, allowing a
meaningful swing on extreme days but a small one on mild days.
Whether 0.3 should be raised depends on calibration against real
outcome data — the sensitivity script provides the raw numbers for
that decision.

## Immediate Formula Work

1. Replace full-AQI heat multiplication with ozone-specific adjustment.
2. Return per-pollutant AQI components.
3. Add dominant pollutant and pollution confidence.
4. Move calculation logs behind debug mode.
5. Add unit tests for AQI breakpoints, NDT, RDS, and CCRI.
