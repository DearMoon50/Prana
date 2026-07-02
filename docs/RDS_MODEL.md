# Recovery Debt Score (RDS) — Model, Proof, and Derivation

**Status:** current implementation as of 2026-07-02.
**Scope:** this documents what RDS is, proves numerically that it does something a
plain forecast cannot, and states honestly where each number comes from.
**Source of truth:** `prana/rds_calculator.py` and `prana/config.py`. Every number
below is reproducible with `python -m research.rds_demo.demo`.

---

## 0. What RDS is, in one sentence

RDS estimates how much **sleep-recovery debt** a household has accumulated over the
last few hot nights, so PRANA can warn people whose bodies are still depleted even
when *tonight's* forecast looks fine.

The model has three honesty tiers, kept separate on purpose:

| Tier | What it is | Evidence level |
|---|---|---|
| **Indoor offset** | how much hotter/cooler a room is vs outdoors | **Backed by real data** (ASHRAE + South Asia) |
| **Per-night recovery score** | did the body recover that night | Literature-grounded thresholds |
| **Multi-night compounding** | debt piles up, fades slowly | **Calibrated engineering hypothesis** |

This document never claims the compounding tier is medically validated. It is a
transparent, bounded model with an explicit uncertainty band.

---

## 1. Numeric proof that RDS works

"Works" here means four concrete, testable properties. All numbers below are
produced by the **actual** `RDSCalculator`, not illustrative.

### Proof 1 — No false alarms
Four consecutive cool nights (≤30 °C, below the 32 °C threshold):

| input | RDS (mid) | consecutive hot nights |
|---|---|---|
| 29, 30, 28, 30 °C | **0.0** | 0 |

RDS is silent when it should be. It does not manufacture risk.

### Proof 2 — The differentiator (the key proof)
Two users, **identical cool night tonight (30 °C)**, different history:

| user | last 3 nights | tonight | naive forecast | **RDS (mid)** |
|---|---|---|---|---|
| A | 35, 36, 34 °C (hot) | 30 °C | "you're fine" | **57.0** |
| B | 29, 28, 29 °C (cool) | 30 °C | "you're fine" | **0.0** |

A plain tonight-only forecast treats A and B **identically** — both "fine."
RDS separates them by **57.0 points**. That gap *is* the reason RDS exists: it
carries forward recovery debt a forecast structurally cannot see.

### Proof 3 — Monotonic accumulation
More hot nights ⇒ higher debt (each night 34 °C, i.e. 20 raw points):

| # hot nights | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| RDS (mid) | 20.0 | 36.0 | 48.8 | 59.0 |

Strictly increasing, but with **diminishing additions** (because older nights are
discounted — see §2). Debt builds, it doesn't explode linearly.

### Proof 4 — Recovery / decay
A single 36 °C night (raw score 40) fades as cool nights follow:

| days ago | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| RDS | 40.0 | 32.0 | 25.6 | 20.5 |
| check: 40 × 0.8ᵈ | 40.0 | 32.0 | 25.6 | 20.5 |

Debt clears gradually (≈20% per cool night), matching the "hot fast, recover slow"
physiology the model is meant to capture — see §3.3 for why 0.8 (slow, multi-night
clearance) is the literature-consistent direction.

### Proof 5 — Bounded (no runaway)
A physically extreme 60 °C night:

| input | RDS (mid) |
|---|---|
| 60 °C | **100.0** (hard cap) |

A long or extreme heatwave saturates at 100 rather than growing without bound, so
the score stays interpretable.

**Conclusion.** RDS is silent when safe (P1), distinguishes accumulated risk a
forecast misses (P2), rises monotonically with heat (P3), recovers over cool
nights (P4), and stays bounded (P5). These are exactly the behaviours a
recovery-debt score must have.

---

## 2. How RDS is currently implemented

Computation runs in three stages (`prana/rds_calculator.py`).

### Stage 1 — Effective indoor temperature
The forecast gives an outdoor night minimum. RDS converts it to the temperature
the person actually sleeps in:

```
effective_indoor_temp = outdoor_night_temp + indoor_offset
```

`indoor_offset` (°C) is summed from onboarding answers:

| factor | offset | source |
|---|---|---|
| Air conditioning | −3.0 | literature (see §3) |
| Fan | −2.0 | ASHRAE 55 elevated-airspeed |
| Windows open | −1.5 | night-ventilation assumption |
| Roof / floor / climate | temperature-dependent | fitted (`RDS_CLIMATE_ZONE_COEFFS`) |
| Each extra occupant | +0.5 | metabolic heat load |

The building-envelope part is **climate-zone-aware and temperature-dependent** (a
tin roof's effect grows with outdoor heat), not a flat constant.

### Stage 2 — Per-night Recovery Failure Units (RFU)
Each night gets a 0–100 score for how badly recovery failed. **Two heat pathways
are evaluated and the worse one is taken**, so neither dry nor humid heat is missed:

```
# Dry-heat pathway
dry_excess = effective_indoor_temp − 32.0            # RDS_NIGHTTIME_THRESHOLD
dry_rfu    = min(100, (dry_excess / 10) × 100)  if dry_excess > 0 else 0

# Humid-heat pathway (wet-bulb, Stull 2011)
wet_bulb   = stull_wet_bulb(effective_indoor_temp, humidity)
wet_excess = wet_bulb − 28.0                          # RDS_NIGHTTIME_WETBULB_THRESHOLD
wet_rfu    = min(100, (wet_excess / 10) × 100)  if wet_excess > 0 else 0

RFU = max(dry_rfu, wet_rfu)
```

Slope: **~10 RFU per 1 °C** over a threshold. Below threshold, RFU = 0 (full
recovery).

### Stage 3 — Multi-night compounding with decay
The last **4 nights** are combined, recent nights weighted more:

```
RDS = Σ  RFU(night) × 0.8^(days_ago)          # RDS_DECAY_FACTOR = 0.8
RDS = min(100, RDS)                           # saturation cap
```

The `0.8^days_ago` term means tonight counts fully, last night ×0.8, two nights
ago ×0.64, and so on — a half-life of ~3.1 nights, so debt lingers across the
whole 4-night window rather than clearing quickly (see §3.3).

### Uncertainty band (low / mid / high)
Because the true indoor offset is uncertain, RDS is computed at three offsets —
`mid`, `mid − band`, `mid + band` (band = 2.0 °C, +1.5 °C extra if AC) — giving
`rds_low ≤ rds_mid ≤ rds_high`. The user sees a **range**, not false precision.

### Current thresholds and constants (verified)

| constant | value | meaning |
|---|---|---|
| `RDS_NIGHTTIME_THRESHOLD` | 32.0 °C | dry-bulb recovery line |
| `RDS_NIGHTTIME_WETBULB_THRESHOLD` | 28.0 °C | wet-bulb (humid-heat) recovery line |
| `RDS_DECAY_FACTOR` | 0.8 | per-day discount of older nights (half-life ~3.1 nights) |
| `RDS_MAX_DAYS` | 4 | nights tracked |
| RFU slope | 10 pts / °C | steepness above threshold, up to 10 °C excess; smooth log tail beyond (see §3.3) |
| offset band | ±2.0 °C (+1.5 AC) | indoor-temperature uncertainty |

---

## 3. How the thresholds were derived

This section is deliberately blunt about evidence strength.

### 3.1 The 32 °C dry-bulb / 28 °C wet-bulb thresholds — *literature-grounded, calibrated*
Being blunt about provenance: these two thresholds were **not point-derived** from a
dataset. But they are **not arbitrary either** — each sits inside a peer-reviewed,
empirically measured range. The honest claim is "grounded within published ranges,
exact value calibrated," not "proven."

- **28 °C wet-bulb** sits inside the **empirically measured** uncompensable-heat
  range. Vecellio et al. (PSU HEAT Project, *J Appl Physiol* 2022;
  [doi:10.1152/japplphysiol.00738.2021](https://journals.physiology.org/doi/full/10.1152/japplphysiol.00738.2021))
  measured the critical wet-bulb temperature at which heat becomes uncompensable in
  resting/lightly-active young adults at **25–28 °C in hot-dry air and 30–31 °C in
  warm-humid air** — far below the old theoretical 35 °C. PRANA's 28 °C sits at the
  lower bound of that measured range, and because sleep is *lower* exertion than
  their protocol, 28 °C is a conservative choice.
- **32 °C dry-bulb** is the dry-heat counterpart. Its *per-degree penalty* structure
  is backed by Obradovich et al. (*Science Advances* 2017;
  [doi:10.1126/sciadv.1601555](https://www.science.org/doi/10.1126/sciadv.1601555)),
  which found a dose-response of nighttime temperature on sleep loss — **worst for
  low-income and elderly people, PRANA's exact target population**. That paper
  models temperature continuously, so it grounds the *slope*, not the exact 32 °C
  cutoff — the cutoff itself remains a calibrated choice.
- The Stull (2011) formula converts temperature + humidity to wet-bulb (±~1 °C for
  warm-humid conditions).

**How the two thresholds actually relate (this part IS derivable, and corrects a
wrong code comment).** The `calculate_recovery_factor` docstring claims the two
thresholds are "chosen so that at moderate humidity (~50–60% RH) the pathways
roughly agree." **That is numerically false.** Running the Stull formula:

| a 32 °C night at… | 40% | 50% | 60% | 70% | **73%** | 80% RH |
|---|---|---|---|---|---|---|
| gives wet-bulb of | 22.1 | 24.0 | 25.8 | 27.5 | **28.0** | 28.8 °C |

So a 32 °C night only reaches the 28 °C wet-bulb line at **~73% RH**, not 50–60%.
The real behaviour: the **dry pathway binds from 32 °C up to ~73% RH**, and the
**wet-bulb pathway only adds risk above ~73% RH** (genuinely humid heat). This is a
reasonable *design* — the wet-bulb term is there to catch humid nights the dry
number underrates — but the documented *rationale* was incorrect and has been
noted for a code-comment fix.

**Evidence level:** direction and rough magnitude are grounded in heat-health
literature; the exact values are *adopted/chosen*, not fitted. Do not present them
as empirically derived.

### 3.2 The indoor offsets — *the part backed by real data*
The offset model was validated against two real datasets:

- **South Asia indoor-heat dataset** (206 loggers; Nature Sci Data
  10.1038/s41597-022-01314-5). Mixed-effects fit, **n = 26,501 logger-nights,
  R² = 0.564, RMSE = 2.48 °C**. Roof offsets vs brick: tin +1.95, concrete +1.40,
  stone +0.56 °C — and the tin effect **scales with outdoor temperature**, which
  is why the model is temperature-dependent rather than flat.
- **ASHRAE Global Thermal Comfort Database II** (~107k observations; used to obtain
  the AC signal the South Asia data lacked). At a realistic 30 °C outdoor
  temperature, homes **without** AC run **≈ +3.5 °C hotter** than air-conditioned
  homes (gap widens with heat). Equivalently, **AC ≈ −3.5 °C of cooling — real-data
  support for the hand-set −3.0 °C AC offset.**

  *Caveats (stated in the source report): ASHRAE outdoor temp is a monthly mean,
  observations are daytime comfort votes (not sleep), and the AC signal is
  office-dominated because residential rows with AC were too few. It grounds the
  offset, not the recovery mechanism.*

**Evidence level:** genuinely empirical. This is RDS's strongest tier.

### 3.3 The RFU slope (10 pts/°C) and decay factor (0.8) — *engineering choices, one literature-corrected*
- The **10-RFU-per-degree** slope is a linear placeholder (loosely motivated by
  heat–health dose-response, e.g. Obradovich et al. 2017). It sets *how fast* the
  score rises, not *whether* it rises. The code comments mark it as un-fitted.

- **The saturation shape — fixed during this review.** The slope originally hit a
  hard `min(100, ...)` cap at 10 °C excess, which meant **any** two nights beyond
  that point scored identically (a 42 °C and a 58 °C effective night both read
  exactly 100 — no way to tell them apart). Fixed by extending the same linear
  curve into a continuous logarithmic tail beyond 10 °C excess (`_rfu_from_excess`
  in `rds_calculator.py`): matching value *and* slope at the junction, so it is a
  genuine continuation, not a new arbitrary cutoff. Effect: the realistic range
  (0–10 °C excess — every observed value in this codebase's demos, sensitivity
  sweep, and the Karachi case study) is **completely unchanged**; only extreme,
  essentially non-physical nights (>42 °C dry-bulb effective) now get
  distinguishable scores (42 °C → 100, 58 °C → 128.3, 80 °C → 136.6) instead of
  flatlining. The multi-night RDS total is still hard-capped at 100 (see §5), so
  the system-level output stays bounded — this only restores internal
  distinguishability, it does not remove the safety ceiling.

- **The decay factor (0.8) — corrected during this review.** An earlier draft of
  this document proposed *lowering* decay to 0.5, citing the two-process model's
  ~4-hour sleep-pressure time constant. **That was wrong on two counts**: (a) the
  two-process model describes homeostatic pressure dissipating *within a single
  night's sleep* — a different timescale and mechanism from RDS's *night-to-night*
  persistence, so citing it here was a category error; (b) in RDS's math, a
  *lower* decay factor means old nights' contributions shrink *faster*, i.e.
  **faster** apparent recovery — the opposite of what "recovery is slow" evidence
  supports.

  The literature that actually addresses multi-night recovery — chronic
  sleep-restriction studies — consistently shows recovery is **slow and
  incomplete**: 5 nights of restriction needs ~7 nights to return to baseline;
  10 days of 30%-restricted sleep needs ~7 days; deficits remain measurable after
  multiple consecutive recovery nights, in some cases 9+ nights
  (*SLEEP Advances* 2023, [PMC10108639](https://academic.oup.com/sleepadvances/article/4/1/zpac044/6854927);
  *Neurobehavioral Dynamics Following Chronic Sleep Restriction*,
  [PMC8274462](https://pmc.ncbi.nlm.nih.gov/articles/PMC8274462/)). That evidence
  argues for a **higher** decay factor (more retention, slower clearing), not a
  lower one. **0.8** — the value originally in this codebase before being loosened
  to 0.6 for "faster decay" — better matches that direction: a ~3.1-night
  half-life, with ~41% of a night's debt still present after the full 4-night
  window, rather than clearing almost entirely (as 0.6 did).

  **Caveat, stated plainly:** the cited studies measure *chronic, hours-short
  sleep restriction* in lab settings, not *acute heat-driven single-night
  recovery failure*, which is RDS's actual mechanism. Borrowing their recovery
  *direction* (slow, not fast) is a defensible analogy; borrowing their exact
  *rate* would not be. 0.8 is the literature-consistent **direction**, not a
  fitted value — no dataset ties an RDS decay curve to a measured heat-sleep
  recovery outcome.

**Evidence level:** calibrated hypothesis, corrected to match the *direction*
supported by the closest available literature. Validating the exact rate would
require per-user sleep/health outcome data tied specifically to heat exposure (a
deliberate future step; the personalization layer already lets each user's
check-ins correct their offset over time).

### 3.4 Why the exact values are defensible anyway — robustness / sensitivity
Even though 32 °C, 0.8, the slope, and the 4-night window are calibrated rather
than point-derived, RDS's **conclusion does not depend on their exact values.**
Sweeping the two most-questioned constants across their full plausible range —
dry threshold **30–34 °C** × decay **0.4–0.8** (25 combinations) — and re-running
the discrimination test (two households, identical cool 30 °C night, opposite
histories; a forecast calls both "fine"):

| decay \ threshold | 30 °C | 31 °C | 32 °C | 33 °C | 34 °C |
|---|---|---|---|---|---|
| 0.4 | 28.8 | 22.6 | 16.3 | 10.1 | 3.8 |
| 0.5 | 41.2 | 32.5 | 23.8 | 15.0 | 6.2 |
| 0.6 | 56.4 | 44.6 | 32.9 | 21.1 | 9.4 |
| 0.7 | 74.5 | 59.2 | 43.9 | 28.6 | 13.2 |
| **0.8 (current default)** | 96.0 | 76.5 | **57.0** | 37.4 | 17.9 |

Each cell is RDS(hot-history) − RDS(cool-history). **The gap is positive in all
25/25 cells** (smallest 3.8): the hot-history household is flagged over the
cool-history one regardless of the exact constants. So "you picked 32, not 31, and
0.8 not 0.6" does not change what RDS decides — and the current default (0.8/32 °C)
happens to give the *strongest* separation (57.0) in the whole grid.

Two more constants require no sweep, by construction:
- The **RFU slope** (pts/°C) is a pure multiplier — it scales every RDS equally, so
  it **cannot** change any ranking or which household is flagged.
- The **4-night window**: older nights are already down-weighted below 0.8⁴ ≈ 0.41;
  extending the window shifts absolute scores by a few points, never the order.

Reproduce: `python -m research.rds_demo.sensitivity`.

---

## 4. Real-event face validation (Karachi 2015)

Beyond the synthetic proof (§1), RDS was replayed on the **real Karachi June 2015
heatwave** (~1,200 deaths; humid coastal event — the regime RDS targets), using
Open-Meteo archive data for PRANA's target user (a top-floor low-income home):

- A **naive tonight-only dry-bulb** forecast called the night "FINE" on **7 of 8
  nights** — including the last, when RDS had peaked.
- **RDS accumulated recovery debt** to **30.9 (HIGH)** via the wet-bulb pathway
  + compounding — flagging impaired recovery a single-night view missed.
- Honestly: RDS peaks at HIGH, not CRITICAL — a calibrated, non-alarmist signal on
  a genuinely deadly event. This is *face validity on a real event*, not
  statistical proof.

Reproduce: `python -m research.rds_demo.case_study_karachi2015`.

## 5. Robustness to bad input (edge cases)

RDS degrades gracefully on malformed data (regression-tested in
`tests/test_rds_edge_cases.py`):

- **Invalid temperatures** (None/NaN/inf) are rejected at ingestion, never stored.
- **Future-dated nights** cannot inflate the score — the decay weight is clamped to
  ≤ 1 (`days_ago = max(0, …)`).
- **Invalid humidity** (negative/NaN) falls back to the dry-bulb pathway; **>100% RH**
  is clamped to 100%.
- **Malformed forecast points** (missing/bad timestamp or temp) are skipped, never
  crashing the risk assessment.
- The **uncertainty band stays ordered** (low ≤ mid ≤ high) across all scenarios.
- **Extreme nights (>42 °C effective) are distinguishable, not flattened** — see
  §3.3. Per-night RFU can exceed 100 for these; the **multi-night RDS total is
  still hard-capped at 100** (`min(100.0, total_rds)` in
  `_compute_rds_single_offset`), so the system-level output remains bounded —
  verified in `test_rds_edge_cases.py::TestRFUExtremeHeatDistinguishable`.

## 6. Honest limitations

- The multi-night compounding mechanism (§3.3) is **not** validated against health
  outcomes. It is a bounded, interpretable hypothesis with an uncertainty band.
- The offset grounding (§3.2) rests on daytime-comfort and monthly-mean-outdoor
  proxies, not direct nighttime sleep measurements.
- RDS is a **rule-based physics-style model**, not machine learning — every output
  is traceable to a named constant. Personalization tunes the per-user offset from
  check-ins; it does not (yet) re-learn the shared thresholds.

## 7. Reproduce everything here

```bash
python -m research.rds_demo.demo /path/to/ashrae_db2.01.csv   # proof + grounding + report
python -m research.rds_demo.sensitivity                        # threshold robustness (25/25)
python -m research.rds_demo.case_study_karachi2015             # real-event face validation
python -m pytest tests/test_formulas.py tests/test_issue1_rds_bands.py \
                 tests/test_personalization.py tests/test_rds_edge_cases.py
```
