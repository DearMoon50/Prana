# RDS Suitability Demonstration — Design

**Date:** 2026-07-02
**Status:** Design (pre-implementation)
**Author:** brainstormed with Claude

## Purpose

PRANA is an MVP. The goal of this work is **not** to scientifically validate the
full Recovery Debt Score (RDS) model. It is narrower and achievable: **prove RDS
is a real, correct, data-grounded, and useful component that is suitable to ship
in the main PRANA application, and demonstrate it.**

The output is an *evidence package* — a reproducible demo plus a short report —
that lets us honestly say: "RDS is correct, its inputs are grounded in real
data where they can be, and it catches something a plain forecast misses. It is
ready to use in PRANA."

## Background: the three layers of RDS (and what is provable)

Established during scoping (see `prana/rds_calculator.py`, `prana/config.py`,
`prana/personalization.py`):

- **Layer 1 — recovery mechanism** (32°C dry / 28°C wet-bulb thresholds, decay
  factor, multi-night compounding). The *novel* part. **Unvalidated** — the RFU
  slope is a self-admitted placeholder; decay/compounding is a modeling
  hypothesis, tested only for self-consistency. **Out of scope to validate.**
- **Layer 2 — indoor offset** (how much hotter a room is than outdoors, by
  AC/roof/floor/climate). The **only part with real data behind it** (South Asia
  mixed-effects: R²=0.564, RMSE=2.48°C). **This is the exhibit.**
- **Layer 3 — per-user learning** (`personalization.py` Bayesian update).
  Already built and working; learns per-user only. **Out of scope to extend.**

The demonstration deliberately proves only what an MVP can honestly prove, and
labels the rest as acknowledged limitations rather than hiding them.

## The three claims the demo must establish

1. **Correct** — RDS computes what it specifies, deterministically, tests green.
2. **Grounded** — the indoor offset (esp. the AC coefficient PRANA currently
   hand-sets at −3.0°C) is fit from real datasets, not guessed.
3. **Differentiated** — a concrete scenario where RDS stays elevated from
   accumulated recovery debt while a plain "is it hot tonight?" forecast says
   "you're fine." ("RDS caught what a forecast missed.")

## Scope

### In scope

- **Workstream A — Correctness.** Fix the 2 failing RDS tests
  (`tests/test_formulas.py::RDSTests`) and the bugs surfaced by the current
  on-disk refactor of `rds_calculator.py`:
  - dead code: `indoor_offset_mid`/`indoor_offset_low/high` computed at
    `calculate_rds` (~L232) but ignored by the per-night offset path.
  - stale debug logging referencing removed variables.
  - decay-factor inconsistency: `config.RDS_DECAY_FACTOR = 0.6` vs tests that
    encode the older 0.8 and a flat +3.5 offset — reconcile the intended value
    and update whichever is stale (verify by hand-tracing, do not blindly match).
  - confirm `min(100.0, total_rds)` saturation cap is intended vs the tests.

- **Workstream B — Dataset grounding (both datasets, briefly).**
  - **ASHRAE DB II (headline):** new `research/indoor_heat/adapters/ashrae/`
    adapter over `ashrae_db2.01.csv` (~107k rows; 77,435 with indoor+outdoor
    temp). Produces the canonical schema directly (survey data, not time-series
    — skips the time-series `core/` steps), then feeds existing `regression.py`.
    Primary output: the **cooling-strategy (AC / Naturally Ventilated /
    Mixed-Mode) offset by Köppen climate zone** — the AC coefficient South Asia
    structurally could not provide.
  - **South Asia (corroboration):** reuse the already-fit result (R²=0.564)
    from `research/indoor_heat`. No new data work.

- **Workstream C — Demonstration.** A runnable
  `python -m research.rds_demo` (exact module path TBD in plan) that:
  1. runs a scripted multi-night scenario (e.g. 3 hot nights → 1 cooler night)
     and prints RDS (low/mid/high) vs a naive tonight-only forecast verdict,
     showing the divergence;
  2. prints the dataset-grounding numbers (ASHRAE AC/cooling offset + CI;
     South Asia R²/coeffs as corroboration);
  3. writes a short markdown report capturing both, plus an explicit
     "acknowledged limitations" section (Layer 1 unvalidated; ASHRAE is
     daytime-comfort & monthly-outdoor; office-heavy building mix).

### Out of scope (explicitly, to protect the MVP)

- Validating Layer 1 (compounding/decay/threshold) against health/sleep outcomes.
- The hierarchical / partial-pooling upgrade to personalization (Layer 3).
- Any live WhatsApp / app-integration demo (script + report only).
- Wiring new coefficients into PRANA config — that is a *separate, deliberate*
  follow-up gated on the go/no-go bar below.

## ASHRAE adapter — data reality (verified against the actual file)

| canonical | ASHRAE source | note |
|---|---|---|
| `indoor_temp` | `Air temperature (C)` | response (92.9% coverage) |
| `outdoor_temp` | `Outdoor monthly air temperature (C)` | ⚠️ **monthly mean**, not nightly (73.7%) |
| `cooling_strategy` | `Cooling startegy_building level` | AC 32k / NV 47k / MM 26k — **the new signal** |
| `climate_zone` | `Koppen climate classification` | 100% — hierarchical grouping |
| `building_type` | `Building type` | office 63% / classroom 17% / **housing only ~10k** |
| `country`, `city` | `Country`, `City` | secondary grouping |
| `fan`, `window` | `Fan` (12%), `Window` (20%) | thin covariates |
| `humidity`, `tsv` | `Relative humidity (%)`, `Thermal sensation` | covariate / outcome |

Model: `indoor_temp ~ outdoor_temp * cooling_strategy + fan + window`, random
intercept + slope grouped by `climate_zone` (reuses `regression.py`).

**Headline runs on the residential subset**; office/classroom reported as a
labeled sensitivity check, not the primary number.

## Honesty boundaries (must appear in the report)

- ASHRAE is a **daytime, occupied, comfort-survey** dataset; TSV ≠ sleep
  recovery. It grounds the **offset**, not the recovery mechanism.
- ASHRAE outdoor is a **monthly mean** — coarser than PRANA's nightly outdoor;
  the offset is "indoor vs monthly-avg outdoor," labeled as such.
- ASHRAE is **office-heavy**; the residential subset is what's relevant to homes.
- Layer 1 remains a **calibrated hypothesis with uncertainty bands**, not a
  validated score. The demo never claims otherwise.

## Go / no-go bar (for a later, separate integration decision)

Only recommend wiring ASHRAE-derived coefficients into PRANA `config.py` if:
(a) the residential-subset fit is stable out-of-sample, AND
(b) the AC-offset confidence interval is tight enough to beat a hand-set guess.
Otherwise the honest output is "keep the literature value; here's the evidence
and why." This decision is **not** part of this work — this work only produces
the evidence to make it.

## Architecture / isolation

- ASHRAE work is an **adapter under the existing `research/indoor_heat/`**, not a
  new top-level tree — reuses `regression.py` and `validate.py`; the raw CSV
  stays git-ignored (lives in scratchpad / `data/`, never committed).
- Correctness fixes are confined to `prana/rds_calculator.py`, `prana/config.py`,
  and the two test modules.
- The demo is a standalone research script depending on the public
  `RDSCalculator` API + the regression outputs — it does not modify PRANA
  runtime behavior.

## Success criteria

- All RDS tests green.
- ASHRAE adapter produces a fitted cooling-strategy offset (with CI) on the
  residential subset, comparable to the South Asia baseline.
- `rds_demo` runs end-to-end and emits the comparison + report.
- The report states the three claims with evidence, and the limitations plainly.
