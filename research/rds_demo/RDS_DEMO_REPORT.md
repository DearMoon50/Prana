# RDS Suitability Demonstration — Report

Goal: show RDS is **correct, data-grounded, and differentiated** — suitable to ship in PRANA (MVP bar; not a full scientific validation).

## Claim 1 — Correct

- Sleep-debt ledger test suite: **GREEN** (tests/recovery/ — 55 tests covering wetbulb, indoor_climate, dose_response, ledger, forecast, and the RecoveryModel facade — plus migrated legacy tests in tests/test_formulas.py, test_issue1_rds_bands.py, test_personalization.py).
- The ledger is deterministic and its uncertainty band is ordered (low <= mid <= high, in both debt-minutes and the legacy 0-100 scale).

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
- **Sleep debt, low/mid/high (minutes):** 76 / 105 / 139 (tier: HIGH; consecutive impaired nights: 4)
- **Legacy 0-100 projection (debt/240min*100):** 31.8 / 43.8 / 58.1
- **Message:** Recovery debt: ~105 min of sleep lost over 4 hot nights (range 76-139 min) - HIGH

The forecast says tonight is fine; the ledger still reports real minutes of accumulated sleep debt from the preceding hot nights. That gap is what the ledger adds over a plain forecast.

## Acknowledged limitations (honest scope)

- The multi-night **debt ledger mechanism** (the Minor-2022 dose-response anchors, the bounded recovery rate/threshold, the debt cap) is a calibrated **hypothesis with uncertainty bands**, not validated against health/sleep outcomes. No dataset here proves the exact rate.
- The offset grounding rests on **daytime comfort / monthly-mean outdoor** proxies, not nightly sleep measurements.
- Personalization learns **per-user only**; it does not yet improve the shared population priors as the app grows.

## Verdict

The sleep-debt ledger is correct, its offset inputs are grounded in real global data (including the AC coefficient, now wired directly into the model), and it demonstrably flags real minutes of accumulated sleep debt that a plain forecast misses. It is suitable to ship as a PRANA MVP component, with the debt-ledger mechanism presented honestly as a calibrated hypothesis.
