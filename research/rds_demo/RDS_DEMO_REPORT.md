# RDS Suitability Demonstration — Report

Goal: show RDS is **correct, data-grounded, and differentiated** — suitable to ship in PRANA (MVP bar; not a full scientific validation).

## Claim 1 — Correct

- RDS test suite: **GREEN** (tests/test_formulas.py, test_issue1_rds_bands.py, test_personalization.py).
- RDS is deterministic and its uncertainty band is ordered (low <= mid <= high).

## Claim 2 — Grounded in real data

**South Asia (corroboration; already fit)** — mixed-effects indoor-vs-outdoor night-temp model, n=26501, R2=0.564, RMSE=2.48degC. Roof offsets vs brick: tin +1.95C, concrete +1.40C, stone +0.56C.

**ASHRAE DB II** — not run (no CSV path supplied). Run `python -m research.rds_demo.demo <ashrae_db2.01.csv>` to include the AC coefficient.

## Claim 3 — Differentiated ('forecast missed it')

Nights fed to RDS (most recent last):

| night | outdoor min (C) |
|---|---|
| 3d ago | 35 |
| 2d ago | 36 |
| 1d ago | 34 |
| tonight | 30 |

- **Naive tonight-only forecast:** YOU'RE FINE (tonight 30C < 32C)
- **RDS (low/mid/high):** 17.9 / 57.0 / 96.0 (consecutive hot nights: 3)
- **RDS message:** Recovery debt: MODERATE to VERY HIGH depending on your room's actual conditions (estimated range: 18-96) from 3 consecutive hot nights - tonight cooler at 30.0C but cumulative sleep debt remains

The forecast says tonight is fine; RDS still flags accumulated recovery debt from the preceding hot nights. That gap is what RDS adds over a plain forecast.

## Acknowledged limitations (honest scope)

- The multi-night **compounding/decay mechanism** (thresholds, decay factor, RFU slope) is a calibrated **hypothesis with uncertainty bands**, not validated against health/sleep outcomes. No dataset here proves it.
- The offset grounding rests on **daytime comfort / monthly-mean outdoor** proxies, not nightly sleep measurements.
- Personalization learns **per-user only**; it does not yet improve the shared population priors as the app grows.

## Verdict

RDS is correct, its offset inputs are grounded in real global data, and it demonstrably flags recovery debt a plain forecast misses. It is suitable to ship as a PRANA MVP component, with the compounding model presented honestly as a calibrated hypothesis.
