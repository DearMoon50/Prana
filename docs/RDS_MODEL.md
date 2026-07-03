# Sleep-Debt Ledger (RDS) — Model, Proof, and Derivation

**Status:** current implementation as of 2026-07-03 (sleep-debt-ledger rebuild).
**Scope:** this documents what the sleep-debt ledger is, proves numerically that
it does something a plain forecast cannot, and states honestly where each
number comes from.
**Source of truth:** `prana/recovery/` (`indoor_climate.py`, `dose_response.py`,
`ledger.py`, `forecast.py`, `model.py`, `wetbulb.py`) and `prana/config.py`.
Every number below is reproducible with `python -m research.rds_demo.demo`.

---

## 0. What the ledger is, in one sentence

The ledger estimates how many **minutes of sleep** a household has lost to heat
over the last few nights and carries that debt forward, so PRANA can warn
people whose bodies are still depleted even when *tonight's* forecast looks
fine.

This is a rebuild of the original "Recovery Debt Score" (RDS). The API keeps
the legacy name and a 0-100 projection for backward compatibility (see §2), but
internally the score is now a **physical quantity — minutes of sleep lost —
not an abstract 0-100 number**. That change was the point of the rebuild: a
score with no units can't be checked against anything; minutes can.

The model has three honesty tiers, kept separate on purpose:

| Tier | What it is | Evidence level |
|---|---|---|
| **Indoor offset** | how much hotter/cooler a room is vs outdoors | **Backed by real data** (ASHRAE + South Asia), AC term now wired directly into the model |
| **Per-night sleep loss** | minutes of sleep lost that night | Anchored to a published wearable-sleep dose-response curve |
| **Multi-night debt ledger** | debt piles up, clears slowly and only on genuinely cool nights | **Calibrated engineering hypothesis** |

This document never claims the debt-ledger tier is medically validated. It is a
transparent, bounded model with an explicit uncertainty band.

---

## 1. Numeric proof that the ledger works

"Works" here means five concrete, testable properties. All numbers below are
produced by the **actual** `RecoveryModel`, not illustrative.

### Proof 1 — Graduated response to marginal heat (no artificial cliff)
Four nights near the old dry-bulb threshold (29, 30, 28, 30 °C — none reaches
the old 32 °C cutoff):

| input | debt (mid, minutes) |
|---|---|
| 29, 30, 28, 30 °C | **48.5** |

This is a deliberate change from the old model, which scored these nights
**0** because they sat below a hard 32 °C cliff. The new dose-response curve is
continuous (§3.1): even a 28-30 °C night costs some sleep, so the ledger no
longer manufactures a false "all clear" for genuinely marginal heat. A
household with four consecutive 28-30 °C nights is not in crisis, but it is not
at zero either — 48.5 minutes is a LOW-to-MODERATE reading (see tiers, §2),
not a false alarm.

### Proof 2 — The differentiator (the key proof)
Two households, **identical cool night tonight (30 °C)**, different history:

| user | last 3 nights | tonight | naive forecast | **debt (mid, minutes)** |
|---|---|---|---|---|
| A | 35, 36, 34 °C (hot) | 30 °C | "you're fine" | **105.0** |
| B | 29, 28, 29 °C (cool) | 30 °C | "you're fine" | **46.0** |

A plain tonight-only forecast treats A and B **identically** — both "fine."
The ledger separates them by **59.0 minutes**. That gap *is* the reason the
ledger exists: it carries forward real sleep debt a forecast structurally
cannot see.

### Proof 3 — Monotonic accumulation
More hot nights ⇒ more debt (each night 34 °C):

| # hot nights | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| debt (mid, min) | 26.0 | 52.0 | 78.0 | 104.0 |

Strictly increasing and, at this temperature, close to linear (34 °C sits on a
near-linear stretch of the dose-response curve — see §3.1). Debt genuinely
builds with repeated heat exposure.

### Proof 4 — Recovery
A single 36 °C night (loses 35 min) fades as cool nights follow:

| nights after | 0 (that night) | +1 cool (20 °C) | +2 cool | +3 cool |
|---|---|---|---|---|
| debt (min) | 35.0 | 0.0 | 0.0 | 0.0 |

A night that itself loses less than `RECOVERY_NIGHT_LOSS_THRESHOLD_MIN` (5 min
— i.e. a genuinely cool, recovering night) clears a fixed
`RECOVERY_PER_COOL_NIGHT_MIN` (45 min) of debt. Here the 35-minute debt clears
in a single cool night because 45 > 35. A larger debt clears in proportionally
more cool nights — e.g. a maxed-out 240-minute debt takes about 6 consecutive
cool nights (240 / 45 ≈ 5.3, rounded up) to fully clear, matching the "hot
fast, recover slow" physiology the model is meant to capture (see §3.2 for why
recovery is bounded and gated, not a percentage decay).

### Proof 5 — Bounded (no runaway)
A physically extreme heatwave:

| input | debt (mid, min) |
|---|---|
| single 60 °C night | 60.0 |
| 7 consecutive 60 °C nights | **240.0** (hard cap) |

A long or extreme heatwave saturates at the configured cap
(`RECOVERY_DEBT_CAP_MIN = 240`) rather than growing without bound, so the score
stays interpretable — while a single extreme night is still fully
distinguishable from a sustained one (60.0 vs 240.0), unlike the old model's
per-night RFU cap, which flattened any two nights past a fixed excess to the
same score.

**Conclusion.** The ledger responds gradually to marginal heat instead of
manufacturing a false all-clear (P1), distinguishes accumulated risk a
forecast misses (P2), rises monotonically with heat (P3), recovers over
genuinely cool nights (P4), and stays bounded (P5). These are exactly the
behaviours a sleep-debt ledger must have.

---

## 2. How the ledger is currently implemented

Computation runs in three stages, each its own module under `prana/recovery/`.

### Stage 1 — Effective indoor temperature (`indoor_climate.py`)
The forecast gives an outdoor night minimum. The ledger converts it to the
temperature the person actually sleeps in:

```
effective_indoor_temp = outdoor_night_temp + indoor_offset
```

`indoor_offset` (°C) is summed from onboarding answers:

| factor | offset | source |
|---|---|---|
| Air conditioning | temperature-dependent (~-3.5 °C at 30 °C outdoor, widening with heat) | **wired directly from ASHRAE DB II** (see §3.3) — `RDS_ASHRAE_AC_BASELINE=-1.5`, `RDS_ASHRAE_AC_INTERACTION=-0.0667` |
| Fan | -2.0 | ASHRAE 55 elevated-airspeed |
| Windows open | -1.5 | night-ventilation assumption |
| Roof / floor / climate | temperature-dependent | fitted (`RDS_CLIMATE_ZONE_COEFFS`) |
| Each extra occupant | +0.5 | metabolic heat load |

The building-envelope part is **climate-zone-aware and temperature-dependent**
(a tin roof's effect grows with outdoor heat), not a flat constant. Structural
cooling is capped at -4.0 °C (physically, structure and radiative sky cooling
cannot zero out an extreme air mass).

### Stage 2 — Per-night minutes of sleep lost (`dose_response.py`)
Each night maps to **minutes of sleep lost**, via a continuous piecewise-linear
curve anchored to Minor et al. 2022 (One Earth; see §3.1). Humidity is folded
in by comparing the dry-bulb effective temperature against a wet-bulb-derived
equivalent and taking the hotter reading, so a humid night is never underrated:

```
minutes_lost(effective_temp, humidity) -> float   # continuous, no cliff
```

Slope: roughly accelerating minutes lost as temperature rises (see the anchor
table in §3.1) — not a fixed points-per-degree constant, and **no threshold
below which loss is exactly zero**.

### Stage 3 — Multi-night debt ledger (`ledger.py`)
The last `RECOVERY_WINDOW_NIGHTS` (7) nights are walked chronologically:

```
debt_n = clamp(debt_{n-1} + lost_n - recovered_n, 0, RECOVERY_DEBT_CAP_MIN)

recovered_n = RECOVERY_PER_COOL_NIGHT_MIN if lost_n < RECOVERY_NIGHT_LOSS_THRESHOLD_MIN else 0
```

A night that itself costs less than 5 minutes of sleep counts as "recovering"
and clears a fixed 45 minutes of accumulated debt; any hotter night clears
nothing (you cannot recover on a night you slept badly). This **decoupled**
design (recovery rate and loss curve are independent knobs) replaces the old
`0.8^days_ago` exponential decay and the old unitless 100-point cap — see §3.2
for why the two constants must be independent.

### Legacy-compatible output & uncertainty band
`RecoveryModel.calculate_rds()` returns both the physical-units numbers and a
projection onto the legacy 0-100 scale, so `ccri_calculator` and existing
messaging needed no formula changes:

```
rds_mid = min(100, debt_minutes_mid / RECOVERY_DEBT_CAP_MIN * 100)
```

A full 240-minute debt now maps to exactly 100 on the legacy scale — heat alone
can reach the top of the old scale, fixing a defect in the previous model where
only a check-in adjustment could push the score into its highest tier.

Because the true indoor offset is uncertain, the ledger is computed at three
offsets — `mid`, `mid − band`, `mid + band` (band = 2.0 °C, +1.5 °C extra if
AC) — giving `debt_low ≤ debt_mid ≤ debt_high` (and the same ordering on the
legacy `rds_*` scale). The user sees a **range**, not false precision.

### Current constants (verified against `prana/config.py`)

| constant | value | meaning |
|---|---|---|
| `SLEEP_LOSS_ANCHORS` | see §3.1 | temp → minutes-lost curve, Minor-2022 anchored |
| `RECOVERY_DEBT_CAP_MIN` | 240 min | maximum carried debt (~4h) |
| `RECOVERY_PER_COOL_NIGHT_MIN` | 45 min | debt cleared by one genuinely cool night |
| `RECOVERY_NIGHT_LOSS_THRESHOLD_MIN` | 5 min | a night losing less than this counts as "recovering" |
| `RECOVERY_WINDOW_NIGHTS` | 7 | nights of history the ledger walks |
| `HOT_CLIMATE_SLEEP_MULTIPLIER` | 1.0 (off by default) | knob for Minor's low-income 2.5-3x finding, not yet enabled |
| `RECOVERY_TIER_MODERATE_MIN` / `_HIGH_MIN` / `_SEVERE_MIN` | 30 / 90 / 180 min | tier boundaries |
| `RDS_ASHRAE_AC_BASELINE` / `RDS_ASHRAE_AC_INTERACTION` | -1.5 / -0.0667 | temp-dependent AC offset (≈-3.5 °C at 30 °C outdoor) |
| `RDS_NIGHTTIME_WETBULB_THRESHOLD` | 28.0 °C | wet-bulb equivalence point used to fold humidity into the effective temp |
| offset band | ±2.0 °C (+1.5 AC) | indoor-temperature uncertainty |

Tiers: LOW (<30 min), MODERATE (30-90), HIGH (90-180), SEVERE (≥180, i.e. up to
the 240-min cap).

---

## 3. How the model was derived

This section is deliberately blunt about evidence strength.

### 3.1 The dose-response curve — *anchored to a published wearable-sleep study, not point-derived*
The old model used a hard 32 °C dry-bulb / 28 °C wet-bulb threshold with a
flat 10-points-per-degree slope above it, and scored **zero** below the
threshold. The rebuild replaces this with a continuous curve anchored to
**Minor et al. 2022** (*One Earth*; wearable-sleep data, ~47,000 users, ~7
million nights), which measured minutes of sleep lost per degree of nighttime
warmth, with effects strongest in **hot climates and lower-income countries —
PRANA's target population**.

Anchor points (`SLEEP_LOSS_ANCHORS` in `prana/config.py`), linearly
interpolated between them and flat outside the range:

| effective temp (°C) | minutes lost |
|---|---|
| 20 | 0 |
| 25 | 4 |
| 28 | 9 |
| 30 | 14 |
| 33 | 22 |
| 35 | 30 |
| 40 | 55 |
| 45 | 60 |

The 30 °C anchor (14 min) is the paper's headline number; the surrounding
anchors extend the shape sensibly into the hotter range PRANA's target
population experiences overnight. `HOT_CLIMATE_SLEEP_MULTIPLIER` is a knob for
the paper's separate finding that effects are 2.5-3x larger in low-income/hot
countries — present in the code but **not enabled by default** (multiplier =
1.0), since applying it correctly needs a per-region decision, not a global
flip.

Humidity is folded in by comparing the dry-bulb effective temperature to a
Stull (2011) wet-bulb estimate shifted onto the same scale (the old dry/wet
threshold gap, 32 vs 28 °C, gives the +4 °C shift) and taking whichever
reading is hotter — so a humid night is never scored as if it were dry.

**Evidence level:** the curve's *existence and rough shape* are grounded in a
large published dataset on the exact mechanism (sleep loss from nighttime
heat); the specific anchor values beyond the 30 °C headline number are a
reasonable interpolation/extrapolation, not independently fit.

### 3.2 The debt ledger (recovery rate, threshold, cap) — *calibrated engineering hypothesis*
- **`RECOVERY_DEBT_CAP_MIN` (240 min, ~4h)** replaces the old unitless 100-point
  saturation cap. It bounds the ledger so an arbitrarily long heatwave doesn't
  grow without limit, while (unlike the old per-night RFU cap) a single
  extreme night and a sustained one remain distinguishable below the cap (see
  Proof 5, §1).
- **`RECOVERY_PER_COOL_NIGHT_MIN` (45 min) and `RECOVERY_NIGHT_LOSS_THRESHOLD_MIN`
  (5 min)** are **deliberately decoupled** from each other and from the loss
  curve. An earlier draft of this ledger used a single coupled formula,
  `recovered = max(0, PER − lost)`, with `PER = 45`. That formula is broken:
  because every realistic night loses at least a few minutes (see the anchor
  table), `PER − lost` is almost always positive and comparable in size to
  `lost` itself, so debt would net to zero on nearly every night below ~50 °C —
  the ledger would almost never show meaningful accumulation. The current
  design instead asks a binary question each night — "did this night cost
  less than `RECOVERY_NIGHT_LOSS_THRESHOLD_MIN` (5 min), i.e. was it
  genuinely cool?" — and if so pays down a fixed `RECOVERY_PER_COOL_NIGHT_MIN`
  (45 min) regardless of exactly how little that night cost. This keeps the
  loss curve and the recovery rate independent, so tuning one doesn't silently
  change the other (and doesn't silently change the check-in bound in §3.4,
  which reuses `RECOVERY_PER_COOL_NIGHT_MIN` as its own budget).
- **`RECOVERY_WINDOW_NIGHTS` (7)** — how many nights of history the ledger
  walks. Wider than the old model's 4-night window, to capture a fuller
  picture of a week's sleep debt while the debt cap still bounds the total.

**Evidence level:** the *direction* (recovery should be slow, incomplete, and
gated on genuinely cool nights, not a smooth percentage decay) is consistent
with chronic sleep-restriction literature (recovery from several nights of
restricted sleep is measurably incomplete after multiple recovery nights).
The *exact* rate (45 min/night) and threshold (5 min) are calibrated
engineering choices, not fit to a heat-specific recovery dataset — no dataset
ties an exact ledger recovery rate to a measured heat-driven sleep-recovery
outcome. This is the least-validated tier of the model, and is presented as
such throughout.

### 3.3 The indoor offsets — *the part backed by real data*
The offset model was validated against two real datasets, and — as of this
rebuild — the AC coefficient is **wired directly into the running model**,
not just cited as support for a hand-set number:

- **South Asia indoor-heat dataset** (206 loggers; Nature Sci Data
  10.1038/s41597-022-01314-5). Mixed-effects fit, **n = 26,501 logger-nights,
  R² = 0.564, RMSE = 2.48 °C**. Roof offsets vs brick: tin +1.95, concrete
  +1.40, stone +0.56 °C — and the tin effect **scales with outdoor
  temperature**, which is why the model is temperature-dependent rather than
  flat.
- **ASHRAE Global Thermal Comfort Database II** (~107k observations; used to
  obtain the AC signal the South Asia data lacked). At a realistic 30 °C
  outdoor temperature, homes **without** AC run **≈ +3.5 °C hotter** than
  air-conditioned homes (gap widens with heat). This is now expressed as a
  temperature-dependent term, `RDS_ASHRAE_AC_BASELINE + RDS_ASHRAE_AC_INTERACTION * T`
  (-1.5 and -0.0667 respectively), giving ≈-3.5 °C of AC cooling at 30 °C and
  more cooling as it gets hotter — **replacing the old flat -3.0 °C
  assumption** with the fitted, temperature-dependent coefficient.

  *Caveats (unchanged from before): ASHRAE outdoor temp is a monthly mean,
  observations are daytime comfort votes (not sleep), and the AC signal is
  office-dominated because residential rows with AC were too few. It grounds
  the offset, not the recovery mechanism.*

**Evidence level:** genuinely empirical, and now the model's coefficients
match the fitted numbers exactly rather than approximating them by hand. This
is the ledger's strongest tier.

### 3.4 Bounded check-ins — *fixing a real defect in the previous model*
Sleep check-ins (structured WhatsApp replies) nudge the debt estimate, but the
nudge is **clamped to at most `±RECOVERY_PER_COOL_NIGHT_MIN` (45 minutes)** —
i.e. a self-report can never move the debt by more than one night's worth of
recovery budget. This directly fixes a defect in the old model: there, a
check-in applied a flat delta on the 0-100 scale (up to +45 from stacking
`poor_sleep` + `cooling_issue` + `power_issue`) uncapped relative to the
weather-driven score, so a single bad-sleep report (for any reason — noise,
stress, an unrelated bad night) could out-rank an actual multi-night
heatwave. Under the new bound, the weather-driven debt is always the
dominant signal; a check-in can only refine it within a bounded range.

### 3.5 Why the exact values are defensible anyway — robustness / sensitivity
Even though the recovery rate, threshold, and dose-response anchors are
calibrated rather than point-derived, the ledger's **conclusion does not
depend on their exact values.** Sweeping the ledger's two most-questioned
constants across a wide plausible range — `RECOVERY_PER_COOL_NIGHT_MIN`
30-50 min × `RECOVERY_NIGHT_LOSS_THRESHOLD_MIN` 5-25 min (25 combinations) —
and re-running the discrimination test (two households, identical cool 30 °C
night, opposite histories; a forecast calls both "fine"):

| threshold \ per-night | 30 min | 35 min | 40 min | 45 min | 50 min |
|---|---|---|---|---|---|
| 5 min | 59.0 | 59.0 | 59.0 | 59.0 | 59.0 |
| 10 min | 79.5 | 79.5 | 79.5 | 79.5 | 79.5 |
| 15 min | 75.0 | 70.0 | 65.0 | 60.0 | 55.0 |
| 20 min | 75.0 | 70.0 | 65.0 | 60.0 | 55.0 |
| 25 min | 75.0 | 70.0 | 65.0 | 60.0 | 55.0 |

Each cell is `debt(hot-history) - debt(cool-history)` in minutes. **The gap is
positive in all 25/25 cells** (smallest 55.0 minutes): the hot-history
household is flagged over the cool-history one regardless of the exact
recovery constants. So the precise choice of recovery rate and threshold does
not change what the ledger decides.

The dose-response anchor curve itself is monotonic by construction (see
`tests/recovery/test_dose_response.py`), so it cannot flip which household is
flagged either — it can only scale the size of the gap. `RECOVERY_DEBT_CAP_MIN`
(240 min) only bounds the ceiling; neither history in this comparison
approaches the cap, so it plays no role here.

Reproduce: `python -m research.rds_demo.sensitivity`.

---

## 4. Real-event face validation (Karachi 2015)

Beyond the synthetic proof (§1), the ledger was replayed on the **real Karachi
June 2015 heatwave** (~1,200 deaths; humid coastal event — the regime the
ledger targets), using Open-Meteo archive data for PRANA's target user (a
top-floor low-income home):

- A **naive tonight-only dry-bulb** forecast called the night "FINE" on **7 of
  8 nights** — including the last, when the ledger had peaked.
- **The ledger accumulated sleep debt** to **146 minutes (HIGH)** via the
  wet-bulb pathway + multi-night accumulation — flagging impaired recovery a
  single-night view missed. Debt climbed steadily night over night, tracking
  the humid conditions worsening across the week (18 → 36 → 55 → 75 → 96 →
  116 → 141 → 146 minutes).
- Honestly: the ledger peaks at HIGH, not maxed at the 240-minute cap — a
  calibrated, non-alarmist signal on a genuinely deadly event. This is *face
  validity on a real event*, not statistical proof.

Reproduce: `python -m research.rds_demo.case_study_karachi2015`.

## 5. Robustness to bad input (edge cases)

The ledger degrades gracefully on malformed data (regression-tested in
`tests/recovery/` and the migrated `tests/test_rds_edge_cases.py`):

- **Invalid temperatures** (None/NaN/inf) are rejected at ingestion, never
  stored.
- **Future-dated nights** cannot inflate the debt — the ledger only ever walks
  the stored, deduplicated history chronologically.
- **Invalid humidity** (negative/NaN) falls back to the dry-bulb pathway;
  **>100% RH** is clamped to 100%.
- **Malformed forecast points** (missing/bad timestamp or temp) are skipped,
  never crashing the risk assessment.
- **Timezone-aware night selection**: a run after midnight correctly labels
  the night with the evening it began on (`select_night_date`), fixing a bug
  in the previous model where `datetime.now().date()` could mislabel a
  post-midnight run.
- The **uncertainty band stays ordered** (low ≤ mid ≤ high) across all
  scenarios, in both debt-minutes and the legacy 0-100 projection.
- **Debt stays bounded** at `RECOVERY_DEBT_CAP_MIN` (240 min) even under
  arbitrarily long or extreme heatwaves (see Proof 5, §1).

## 6. Honest limitations

- The multi-night debt-ledger mechanism (§3.2) — the recovery rate, the
  cool-night threshold, and the debt cap — is **not** validated against health
  outcomes. It is a bounded, interpretable hypothesis with an uncertainty
  band.
- The dose-response anchor curve (§3.1) is grounded in a large real dataset on
  the correct mechanism, but the specific anchor values beyond the 30 °C
  headline number are a reasonable interpolation, not independently fit.
- The offset grounding (§3.3) rests on daytime-comfort and monthly-mean-outdoor
  proxies, not direct nighttime sleep measurements.
- The ledger is a **rule-based physics-style model**, not machine learning —
  every output is traceable to a named constant. Personalization tunes the
  per-user indoor offset from check-ins; it does not (yet) re-learn the shared
  dose-response or recovery constants.

## 7. Reproduce everything here

```bash
python -m research.rds_demo.demo /path/to/ashrae_db2.01.csv   # proof + grounding + report
python -m research.rds_demo.sensitivity                        # ledger-constant robustness (25/25)
python -m research.rds_demo.case_study_karachi2015             # real-event face validation
python -m pytest tests/recovery/ tests/test_formulas.py tests/test_issue1_rds_bands.py \
                 tests/test_personalization.py tests/test_rds_edge_cases.py \
                 tests/test_issue7_forecast_validation.py
```
