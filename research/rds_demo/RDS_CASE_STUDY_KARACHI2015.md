# RDS Case Study — Karachi June 2015 Heatwave (face validation)

The Karachi 2015 heatwave killed ~1,200 people. It was a **humid coastal** event: nights stayed hot AND humid, so nighttime recovery failed via the wet-bulb pathway — exactly what RDS is built to catch. We replay the real nightly data for PRANA's target user (a **top-floor low-income home**, which runs hotter indoors).

Data: Open-Meteo historical archive (hourly 2 m temp + RH, nighttime 22:00-06:00 minimum). This is **face validation on a real event, not statistical proof.**

| night | outdoor min | RH | naive dry-bulb (tonight-only) | RDS (mid) | tier |
|---|---|---|---|---|---|
| Jun16 | 28.2 °C | 89% | FINE | 0.0 | LOW |
| Jun17 | 28.5 °C | 86% | FINE | 0.0 | LOW |
| Jun18 | 28.7 °C | 87% | FINE | 0.0 | LOW |
| Jun19 | 29.5 °C | 85% | FINE | 1.2 | LOW |
| Jun20 | 30.0 °C | 84% | FINE | 4.4 | LOW |
| Jun21 | 30.8 °C | 77% | FINE | 6.4 | LOW |
| Jun22 | 32.3 °C | 77% | RISK | 20.3 | MODERATE |
| Jun23 | 29.8 °C | 89% | FINE | 30.9 | HIGH |

## What this shows

- A **naive tonight-only dry-bulb** forecast calls the night **FINE on 7 of 8 nights** — including the last night, when RDS has already climbed to its peak.
- **RDS accumulates recovery debt** across the humid nights, reaching **30.9 (HIGH)** by Jun23 — flagging impaired recovery a single-night view misses.
- The signal comes from the **wet-bulb pathway** (high humidity) plus **multi-night compounding** — RDS's two distinctive mechanisms, on real data.

## Honest limits

- Uses outdoor archive data + a **modeled indoor offset** (top-floor home), not measured bedroom temperature.
- Daily nighttime minimum is a proxy for the sleeping-hours low.
- RDS peaks at MODERATE, not CRITICAL — it is a calibrated, **non-alarmist** signal, not a mortality predictor. This is face validity, not proof.
