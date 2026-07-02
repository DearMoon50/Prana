# RDS Sleep-Debt Ledger Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace PRANA's `RDSCalculator` with a physically-grounded sleep-debt ledger that reports recovery debt in **minutes of sleep lost to heat**, wiring in the already-fitted ASHRAE/South-Asia evidence and fixing the timezone, unreachable-CRITICAL, and check-in-out-signals-weather defects.

**Architecture:** A new `prana/recovery/` package with four focused modules — `indoor_climate` (outdoor→effective-indoor temp, reusing `RDS_CLIMATE_ZONE_COEFFS` + a temp-dependent ASHRAE AC offset), `dose_response` (effective temp + humidity → minutes of sleep lost, anchored to Minor et al. 2022), `ledger` (chronological debt accumulation `debt = clamp(debt + lost − recovery, 0, CAP)`), and `forecast` (tz-aware night selection + forecast parsing). A thin `RecoveryModel` facade preserves the consumer-facing entry points so `prana_system`, `ccri_calculator`, `backend/main`, and `ai_tools/checkin` migrate with minimal churn. The old `prana/rds_calculator.py` is deleted last.

**Tech Stack:** Python 3.9, pydantic-free plain modules, pytest. No new dependencies. Wet-bulb via existing Stull formula (moved, not rewritten).

## Global Constraints

- **Python 3.9 syntax only.** No PEP 604 (`X | Y`) or PEP 585 (`list[str]`) in annotations that are evaluated at runtime; use `typing.Optional`/`typing.List`. (`from __future__ import annotations` is acceptable where a module already uses it.)
- **No ML.** Deterministic + fitted constants only. Every output must trace to a named constant in `prana/config.py`.
- **All new tuning constants live in `prana/config.py`**, not hard-coded in modules.
- **Existing personalization contract is preserved:** `compute_onboarding_temp_offset(onboarding_data, outdoor_temp=None, climate_zone="default")` and `compute_band_width(onboarding_data)` must remain callable with identical signatures and identical return semantics (they are consumed by `backend/main.py::_onboarding_prior_mean/_onboarding_prior_sd` and `prana/personalization.py`).
- **Persistence shape is preserved:** `nighttime_temps` remains a list of `{'date': date, 'temp': float, 'humidity'?: float}` dicts so `prana/database.py::save_user_rds_state/load_user_rds_state` and `models.RDSState` need no migration.
- **`calculate_rds()` return dict must keep the keys** `rds_low`, `rds_mid`, `rds_high`, `consecutive_nights`, `personalized` (consumed by `apply_sleep_checkin_adjustment`, `get_rds_message`, `ccri_calculator`, `prana_system`, and the API response). New keys may be **added** (e.g. `debt_minutes_mid`, `tier`) but none removed.
- **Run the full suite** `python -m pytest` after each task's final step; a task is not done if it reddens a previously-green test that isn't intentionally being rewritten in that task.

---

## File Structure

**New package `prana/recovery/`:**
- `prana/recovery/__init__.py` — exports `RecoveryModel`, `wet_bulb_stull`.
- `prana/recovery/wetbulb.py` — Stull (2011) wet-bulb, moved verbatim from `rds_calculator._stull_wet_bulb`. Single responsibility: temp+RH → wet-bulb.
- `prana/recovery/indoor_climate.py` — `compute_onboarding_temp_offset`, `compute_band_width`, `ashrae_ac_offset`, `effective_indoor_temp`. Single responsibility: outdoor → effective indoor sleeping temperature.
- `prana/recovery/dose_response.py` — `minutes_lost(effective_temp, humidity)` via a piecewise-linear anchor curve. Single responsibility: one night's heat → minutes of sleep lost.
- `prana/recovery/ledger.py` — `accumulate_debt(nights)` chronological ledger. Single responsibility: per-night losses → cumulative debt (minutes).
- `prana/recovery/forecast.py` — tz-aware `estimate_nighttime_conditions_from_forecast`, `select_night_date`. Single responsibility: forecast list + tz → tonight's night min/humidity and the correct calendar date.
- `prana/recovery/model.py` — `RecoveryModel` facade holding `nighttime_temps`, orchestrating the four modules, exposing the consumer API (`add_night_temperature`, `calculate_rds`, `apply_sleep_checkin_adjustment`, `get_rds_message`, `estimate_*`, static `compute_onboarding_temp_offset`/`compute_band_width`).

**Modified consumers:**
- `prana/config.py` — add ledger constants (Task 1).
- `prana/prana_system.py:16,34,152-190,296-297,455-457` — import + instantiate `RecoveryModel`; tz-aware night date.
- `prana/ccri_calculator.py:60-93` — accept debt-minutes → 0-100 recovery score adapter.
- `backend/main.py:316-327,340-353` — repoint the two static-method calls.
- `prana/ai_tools/checkin.py:73` — repoint `estimate_nighttime_conditions_from_forecast`.
- **Deleted:** `prana/rds_calculator.py` (Task 12).

**Tests:** one test module per new module under `tests/recovery/`, plus rewrites of `tests/test_formulas.py`, `tests/test_rds_edge_cases.py`, `tests/test_issue1_rds_bands.py`, `tests/test_personalization.py` as their assertions shift from the old score to the ledger.

**Docs:** `docs/RDS_MODEL.md` rewrite and `research/rds_demo/` re-baseline (Task 12).

---

### Task 1: Ledger constants in config

**Files:**
- Modify: `prana/config.py` (append after line 120, the wet-bulb threshold block)
- Test: `tests/recovery/test_config_constants.py`

**Interfaces:**
- Produces: module-level constants `SLEEP_LOSS_ANCHORS`, `RECOVERY_DEBT_CAP_MIN`, `RECOVERY_PER_COOL_NIGHT_MIN`, `RECOVERY_WINDOW_NIGHTS`, `HOT_CLIMATE_SLEEP_MULTIPLIER`, `RDS_ASHRAE_AC_BASELINE`, `RDS_ASHRAE_AC_INTERACTION`, `RECOVERY_TIER_MODERATE_MIN`, `RECOVERY_TIER_HIGH_MIN`, `RECOVERY_TIER_SEVERE_MIN`. Consumed by every later task.

- [ ] **Step 1: Write the failing test**

Create `tests/recovery/__init__.py` (empty) and `tests/recovery/test_config_constants.py`:

```python
from prana import config


def test_sleep_loss_anchors_are_monotonic_nonneg():
    anchors = config.SLEEP_LOSS_ANCHORS
    temps = [t for t, _ in anchors]
    losses = [m for _, m in anchors]
    assert temps == sorted(temps), "anchor temps must be ascending"
    assert losses == sorted(losses), "minutes-lost must be non-decreasing"
    assert losses[0] == 0.0
    assert all(m >= 0 for m in losses)


def test_ledger_constants_present_and_sane():
    assert config.RECOVERY_DEBT_CAP_MIN == 240
    assert config.RECOVERY_PER_COOL_NIGHT_MIN == 45
    assert config.RECOVERY_WINDOW_NIGHTS == 7
    assert config.HOT_CLIMATE_SLEEP_MULTIPLIER == 1.0
    # tiers strictly ascending and below the cap
    assert 0 < config.RECOVERY_TIER_MODERATE_MIN < config.RECOVERY_TIER_HIGH_MIN \
        < config.RECOVERY_TIER_SEVERE_MIN <= config.RECOVERY_DEBT_CAP_MIN


def test_ashrae_ac_offset_constants_present():
    # temp-dependent AC offset replacing the flat -3.0
    assert config.RDS_ASHRAE_AC_BASELINE == -1.5
    assert config.RDS_ASHRAE_AC_INTERACTION < 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/recovery/test_config_constants.py -v`
Expected: FAIL with `AttributeError: module 'prana.config' has no attribute 'SLEEP_LOSS_ANCHORS'`

- [ ] **Step 3: Add constants to config**

Append to `prana/config.py` immediately after the `RDS_NIGHTTIME_WETBULB_THRESHOLD = 28.0` line:

```python
# ---------------------------------------------------------------------------
# Sleep-debt ledger (RDS rebuild) -- debt is measured in MINUTES of sleep
# lost to heat, replacing the unitless 0-100 score. See docs/RDS_MODEL.md.
# ---------------------------------------------------------------------------

# Per-night dose-response anchors: (effective_indoor_temp_C, minutes_lost).
# Anchored to Minor et al. 2022 (One Earth, ~47k users / 7M nights): a night
# minimum near 30C costs ~14 min of sleep vs a cool baseline; loss accelerates
# with heat. Linearly interpolated between anchors, flat outside the range.
SLEEP_LOSS_ANCHORS = [
    (20.0, 0.0),
    (25.0, 4.0),
    (28.0, 9.0),
    (30.0, 14.0),
    (33.0, 22.0),
    (35.0, 30.0),
    (40.0, 55.0),
    (45.0, 60.0),
]

# Debt ledger dynamics (minutes).
RECOVERY_DEBT_CAP_MIN = 240          # ~4h max carried debt; replaces the old 100 cap
RECOVERY_PER_COOL_NIGHT_MIN = 45     # minutes of debt cleared by one fully-cool night
RECOVERY_WINDOW_NIGHTS = 7           # nights of history the ledger walks
HOT_CLIMATE_SLEEP_MULTIPLIER = 1.0   # knob for Minor's 2.5-3x low-income finding (default off)

# Debt-to-tier thresholds (minutes).
RECOVERY_TIER_MODERATE_MIN = 30.0
RECOVERY_TIER_HIGH_MIN = 90.0
RECOVERY_TIER_SEVERE_MIN = 180.0

# Temp-dependent AC offset (ASHRAE Global Thermal Comfort DB II finding):
# homes WITHOUT AC run ~+3.5C hotter than AC homes at ~30C outdoor, gap widening
# with heat. Expressed as effective indoor cooling = baseline + interaction * T,
# giving ~-3.5C at 30C (base -1.5 + -0.0667*30). Replaces flat RDS_ONBOARDING_AC_OFFSET.
RDS_ASHRAE_AC_BASELINE = -1.5
RDS_ASHRAE_AC_INTERACTION = -0.0667
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/recovery/test_config_constants.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add prana/config.py tests/recovery/__init__.py tests/recovery/test_config_constants.py
git commit -m "feat(recovery): add sleep-debt ledger constants to config"
```

---

### Task 2: Wet-bulb module (moved verbatim)

**Files:**
- Create: `prana/recovery/__init__.py`, `prana/recovery/wetbulb.py`
- Test: `tests/recovery/test_wetbulb.py`

**Interfaces:**
- Produces: `wet_bulb_stull(temp_c, humidity_percent) -> Optional[float]` — identical behaviour to the old `_stull_wet_bulb` (None for None/NaN/inf/negative RH; RH clamped to 100).

- [ ] **Step 1: Write the failing test**

Create `tests/recovery/test_wetbulb.py`:

```python
import math
from prana.recovery.wetbulb import wet_bulb_stull


def test_matches_known_value():
    # 32C at 73% RH -> ~28C wet-bulb (the documented crossover point)
    wb = wet_bulb_stull(32.0, 73.0)
    assert wb is not None
    assert abs(wb - 28.0) < 0.5


def test_rejects_bad_inputs():
    assert wet_bulb_stull(None, 50.0) is None
    assert wet_bulb_stull(30.0, None) is None
    assert wet_bulb_stull(float("nan"), 50.0) is None
    assert wet_bulb_stull(float("inf"), 50.0) is None
    assert wet_bulb_stull(30.0, -5.0) is None


def test_supersaturation_clamped():
    # RH 150 must be treated as 100, not inflate the estimate
    assert wet_bulb_stull(30.0, 150.0) == wet_bulb_stull(30.0, 100.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/recovery/test_wetbulb.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prana.recovery'`

- [ ] **Step 3: Create the package and module**

Create `prana/recovery/__init__.py`:

```python
"""Physically-grounded sleep-debt recovery model (RDS rebuild)."""
from prana.recovery.wetbulb import wet_bulb_stull

__all__ = ["wet_bulb_stull"]
```

Create `prana/recovery/wetbulb.py`:

```python
"""Wet-bulb temperature via Stull (2011). Moved from rds_calculator, unchanged."""
import math
from typing import Optional


def wet_bulb_stull(temp_c, humidity_percent) -> Optional[float]:
    """Wet-bulb temperature, accurate to ~+/-1C for warm-humid conditions.

    Returns None for unusable inputs (None/NaN/inf, or negative RH). RH above
    100% is clamped to 100% rather than allowed to inflate the estimate.
    """
    if temp_c is None or humidity_percent is None:
        return None
    T = float(temp_c)
    RH = float(humidity_percent)
    if not (math.isfinite(T) and math.isfinite(RH)) or RH < 0:
        return None
    RH = min(RH, 100.0)
    return (
        T * math.atan(0.151977 * math.sqrt(RH + 8.313659))
        + math.atan(T + RH)
        - math.atan(RH - 1.676331)
        + 0.00391838 * (RH ** 1.5) * math.atan(0.023101 * RH)
        - 4.686035
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/recovery/test_wetbulb.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add prana/recovery/__init__.py prana/recovery/wetbulb.py tests/recovery/test_wetbulb.py
git commit -m "feat(recovery): wet-bulb module (Stull 2011, moved from rds_calculator)"
```

---

### Task 3: Indoor climate module

**Files:**
- Create: `prana/recovery/indoor_climate.py`
- Test: `tests/recovery/test_indoor_climate.py`

**Interfaces:**
- Consumes: `RDS_CLIMATE_ZONE_COEFFS`, `RDS_ONBOARDING_FAN_OFFSET`, `RDS_ONBOARDING_WINDOW_OFFSET`, `RDS_ONBOARDING_PER_EXTRA_OCCUPANT_OFFSET`, `RDS_INDOOR_OFFSET_BAND_WIDTH`, `RDS_AC_EXTRA_BAND_WIDTH`, `RDS_ASHRAE_AC_BASELINE`, `RDS_ASHRAE_AC_INTERACTION` from config.
- Produces:
  - `ashrae_ac_offset(outdoor_temp) -> float` — temp-dependent AC cooling.
  - `compute_onboarding_temp_offset(onboarding_data, outdoor_temp=None, climate_zone="default") -> float` — **same signature/semantics as the old static method**, but AC term now uses `ashrae_ac_offset`.
  - `compute_band_width(onboarding_data) -> float` — same semantics as old.
  - `effective_indoor_temp(outdoor_temp, offset) -> float` — `outdoor_temp + offset`.

- [ ] **Step 1: Write the failing test**

Create `tests/recovery/test_indoor_climate.py`:

```python
from prana.recovery import indoor_climate as ic


def test_ashrae_ac_offset_is_temp_dependent_and_near_minus_3_5_at_30():
    off = ic.ashrae_ac_offset(30.0)
    assert -3.7 < off < -3.3, off
    # widens (more cooling) with heat
    assert ic.ashrae_ac_offset(35.0) < ic.ashrae_ac_offset(30.0)


def test_no_onboarding_is_zero_offset():
    assert ic.compute_onboarding_temp_offset(None) == 0.0
    assert ic.compute_onboarding_temp_offset({}) == 0.0


def test_ac_uses_ashrae_curve_not_flat_minus_3():
    # AC home at 30C outdoor should get the ASHRAE ~-3.5, not the old flat -3.0
    off = ic.compute_onboarding_temp_offset({"ac": True}, outdoor_temp=30.0)
    assert abs(off - ic.ashrae_ac_offset(30.0)) < 1e-9


def test_structural_cooling_capped_at_minus_4():
    # tin roof + top floor + AC + windows in hot_dry, cool night: still >= -4.0
    off = ic.compute_onboarding_temp_offset(
        {"ac": True, "windows_open": True, "roof_material": "tin", "floor_level": "top"},
        outdoor_temp=22.0, climate_zone="hot_dry",
    )
    assert off >= -4.0


def test_band_width_widens_with_ac():
    from prana.config import RDS_INDOOR_OFFSET_BAND_WIDTH, RDS_AC_EXTRA_BAND_WIDTH
    assert ic.compute_band_width({}) == RDS_INDOOR_OFFSET_BAND_WIDTH
    assert ic.compute_band_width({"ac": True}) == RDS_INDOOR_OFFSET_BAND_WIDTH + RDS_AC_EXTRA_BAND_WIDTH


def test_effective_indoor_temp():
    assert ic.effective_indoor_temp(30.0, -3.5) == 26.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/recovery/test_indoor_climate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prana.recovery.indoor_climate'`

- [ ] **Step 3: Write the module**

Create `prana/recovery/indoor_climate.py`. Port the old static methods, replacing only the AC term. Keep the same `-4.0` structural cap and top-floor `>35C` sky-cooling guard verbatim:

```python
"""Outdoor night temperature -> effective indoor sleeping temperature.

Reuses the fitted South-Asia envelope coefficients (RDS_CLIMATE_ZONE_COEFFS) and
wires the ASHRAE Global Thermal Comfort DB II AC finding as a temp-dependent
offset, replacing the flat -3.0 AC assumption.
"""
from prana.config import (
    RDS_CLIMATE_ZONE_COEFFS,
    RDS_ONBOARDING_FAN_OFFSET,
    RDS_ONBOARDING_WINDOW_OFFSET,
    RDS_ONBOARDING_PER_EXTRA_OCCUPANT_OFFSET,
    RDS_INDOOR_OFFSET_BAND_WIDTH,
    RDS_AC_EXTRA_BAND_WIDTH,
    RDS_ASHRAE_AC_BASELINE,
    RDS_ASHRAE_AC_INTERACTION,
)


def ashrae_ac_offset(outdoor_temp) -> float:
    """Effective indoor cooling from AC, temp-dependent (ASHRAE DB II).

    baseline + interaction * T. ~-3.5C at 30C outdoor, widening with heat.
    """
    T = float(outdoor_temp if outdoor_temp is not None else 25.0)
    return RDS_ASHRAE_AC_BASELINE + RDS_ASHRAE_AC_INTERACTION * T


def compute_onboarding_temp_offset(onboarding_data, outdoor_temp=None, climate_zone="default") -> float:
    """Effective indoor temperature offset from onboarding categorical inputs.

    Same signature and semantics as the legacy RDSCalculator static method, with
    the AC term upgraded from a flat -3.0 to the temp-dependent ASHRAE curve.
    """
    if not onboarding_data:
        return 0.0
    offset = 0.0
    T = float(outdoor_temp if outdoor_temp is not None else 25.0)

    # Cooling devices
    if onboarding_data.get('ac'):
        offset += ashrae_ac_offset(T)
    if onboarding_data.get('fan'):
        offset += RDS_ONBOARDING_FAN_OFFSET
    if onboarding_data.get('windows_open'):
        offset += RDS_ONBOARDING_WINDOW_OFFSET

    # Building envelope (climate-zone-aware, temperature-dependent)
    zone_cfg = RDS_CLIMATE_ZONE_COEFFS.get(climate_zone, RDS_CLIMATE_ZONE_COEFFS["default"])

    roof = str(onboarding_data.get('roof_material', 'brick')).lower()
    roof_cfg = zone_cfg["roof"].get(roof, zone_cfg["roof"].get('brick', {"baseline": 0.0, "interaction": 0.0}))
    offset += roof_cfg['baseline'] + (roof_cfg['interaction'] * T)

    floor = str(onboarding_data.get('floor_level', '')).lower()
    if floor == 'top':
        f_off = zone_cfg["floor"].get("top", 0.0)
        # Longwave sky cooling breaks down under extreme heat: cap cooling at 0 above 35C.
        if T > 35.0 and f_off < 0:
            f_off = 0.0
        offset += f_off

    # Structural cooling cannot physically zero out an extreme air mass.
    offset = max(offset, -4.0)

    # Occupancy (metabolic heat load)
    try:
        occupants = int(onboarding_data.get('occupants', 1) or 1)
    except (TypeError, ValueError):
        occupants = 1
    if occupants > 1:
        offset += (occupants - 1) * RDS_ONBOARDING_PER_EXTRA_OCCUPANT_OFFSET

    return round(offset, 2)


def compute_band_width(onboarding_data) -> float:
    """Half-width of the indoor-offset uncertainty band. AC widens it."""
    width = RDS_INDOOR_OFFSET_BAND_WIDTH
    if onboarding_data and onboarding_data.get('ac'):
        width += RDS_AC_EXTRA_BAND_WIDTH
    return width


def effective_indoor_temp(outdoor_temp, offset) -> float:
    """Effective indoor sleeping temperature = outdoor night min + offset."""
    return outdoor_temp + offset
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/recovery/test_indoor_climate.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add prana/recovery/indoor_climate.py tests/recovery/test_indoor_climate.py
git commit -m "feat(recovery): indoor-climate module with temp-dependent ASHRAE AC offset"
```

---

### Task 4: Dose-response module (minutes of sleep lost)

**Files:**
- Create: `prana/recovery/dose_response.py`
- Test: `tests/recovery/test_dose_response.py`

**Interfaces:**
- Consumes: `SLEEP_LOSS_ANCHORS`, `HOT_CLIMATE_SLEEP_MULTIPLIER`, `RDS_USE_WET_BULB` from config; `wet_bulb_stull` from Task 2.
- Produces: `minutes_lost(effective_temp, humidity=None, hot_climate=False) -> float` — non-negative minutes of sleep lost for one night. Uses the worse of the dry-bulb effective temp and (when humidity known and `RDS_USE_WET_BULB`) a humidity-boosted effective temp so humid nights are not underrated.

- [ ] **Step 1: Write the failing test**

Create `tests/recovery/test_dose_response.py`:

```python
import math
from prana.recovery.dose_response import minutes_lost, _interp_anchor


def test_cool_night_zero_loss():
    assert minutes_lost(20.0) == 0.0
    assert minutes_lost(18.0) == 0.0


def test_30c_costs_about_14_minutes():
    # Minor et al. 2022 anchor
    assert abs(minutes_lost(30.0) - 14.0) < 0.01


def test_interpolates_between_anchors():
    # halfway between 30C(14) and 33C(22) -> 31.5C -> ~18
    assert abs(minutes_lost(31.5) - 18.0) < 0.5


def test_monotonic_nondecreasing():
    prev = -1.0
    for t in [15, 20, 25, 28, 30, 33, 35, 40, 45, 50]:
        m = minutes_lost(float(t))
        assert m >= prev, f"loss dropped at {t}C"
        prev = m


def test_no_cliff_at_32():
    # sub-threshold heat is NOT zero -- continuous curve, unlike the old 32C cliff
    assert minutes_lost(29.0) > 0.0
    assert minutes_lost(31.0) > minutes_lost(29.0)


def test_humidity_raises_effective_loss():
    # a humid 30C night loses at least as much as a dry 30C night
    dry = minutes_lost(30.0, humidity=30.0)
    humid = minutes_lost(30.0, humidity=90.0)
    assert humid >= dry


def test_hot_climate_multiplier():
    base = minutes_lost(33.0, hot_climate=False)
    boosted = minutes_lost(33.0, hot_climate=True)
    # default multiplier is 1.0 so these are equal unless config changes
    from prana.config import HOT_CLIMATE_SLEEP_MULTIPLIER
    assert abs(boosted - base * HOT_CLIMATE_SLEEP_MULTIPLIER) < 1e-9


def test_bad_input_zero():
    assert minutes_lost(float("nan")) == 0.0
    assert minutes_lost(float("inf")) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/recovery/test_dose_response.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prana.recovery.dose_response'`

- [ ] **Step 3: Write the module**

Create `prana/recovery/dose_response.py`:

```python
"""Per-night dose-response: effective indoor temperature -> minutes of sleep lost.

Continuous piecewise-linear curve anchored to Minor et al. 2022 (One Earth):
a night near 30C costs ~14 min of sleep, accelerating with heat. This replaces
the old 32C hard cliff and the un-fitted 10-pts/degC slope. Humidity is folded
in by nudging the effective temperature upward via the wet-bulb signal, so humid
nights are not underrated.
"""
import math
from prana.config import SLEEP_LOSS_ANCHORS, HOT_CLIMATE_SLEEP_MULTIPLIER, RDS_USE_WET_BULB
from prana.recovery.wetbulb import wet_bulb_stull


def _interp_anchor(temp) -> float:
    """Linear interpolation over SLEEP_LOSS_ANCHORS; flat outside the range."""
    anchors = SLEEP_LOSS_ANCHORS
    if temp <= anchors[0][0]:
        return anchors[0][1]
    if temp >= anchors[-1][0]:
        return anchors[-1][1]
    for (t0, m0), (t1, m1) in zip(anchors, anchors[1:]):
        if t0 <= temp <= t1:
            frac = (temp - t0) / (t1 - t0)
            return m0 + frac * (m1 - m0)
    return anchors[-1][1]  # unreachable, defensive


def _humidity_adjusted_temp(effective_temp, humidity) -> float:
    """Blend in humid-heat strain: use the hotter of dry-bulb effective temp and
    a wet-bulb-derived equivalent, so a humid night reads at least as hot as its
    dry-bulb number. Wet-bulb is shifted onto the dry-bulb comfort scale by the
    ~4C gap between the dry (32) and wet (28) thresholds."""
    if not RDS_USE_WET_BULB or humidity is None:
        return effective_temp
    wb = wet_bulb_stull(effective_temp, humidity)
    if wb is None:
        return effective_temp
    # 32C dry ~ 28C wet-bulb -> add the 4C offset to compare on one scale.
    wet_equiv = wb + 4.0
    return max(effective_temp, wet_equiv)


def minutes_lost(effective_temp, humidity=None, hot_climate=False) -> float:
    """Minutes of sleep lost for one night at the given effective indoor temp."""
    if effective_temp is None or not math.isfinite(float(effective_temp)):
        return 0.0
    t = _humidity_adjusted_temp(float(effective_temp), humidity)
    minutes = _interp_anchor(t)
    if hot_climate:
        minutes *= HOT_CLIMATE_SLEEP_MULTIPLIER
    return max(0.0, minutes)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/recovery/test_dose_response.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add prana/recovery/dose_response.py tests/recovery/test_dose_response.py
git commit -m "feat(recovery): dose-response curve (minutes lost, Minor 2022 anchored)"
```

---

### Task 5: Ledger module (chronological debt accumulation)

**Files:**
- Create: `prana/recovery/ledger.py`
- Test: `tests/recovery/test_ledger.py`

**Interfaces:**
- Consumes: `RECOVERY_DEBT_CAP_MIN`, `RECOVERY_PER_COOL_NIGHT_MIN` from config; `minutes_lost` from Task 4.
- Produces: `accumulate_debt(nights) -> float` where `nights` is a list of dicts `{'effective_temp': float, 'humidity': Optional[float], 'hot_climate': bool}` **in chronological order (oldest first)**. Returns final debt in minutes, clamped to `[0, RECOVERY_DEBT_CAP_MIN]`. Recovery on a night is `RECOVERY_PER_COOL_NIGHT_MIN` scaled down by how much sleep that night itself cost (a hot night clears little debt).

- [ ] **Step 1: Write the failing test**

Create `tests/recovery/test_ledger.py`:

```python
from prana.recovery.ledger import accumulate_debt
from prana.config import RECOVERY_DEBT_CAP_MIN


def _night(temp, humidity=None, hot_climate=False):
    return {"effective_temp": temp, "humidity": humidity, "hot_climate": hot_climate}


def test_all_cool_nights_zero_debt():
    nights = [_night(20.0) for _ in range(5)]
    assert accumulate_debt(nights) == 0.0


def test_single_hot_night_adds_its_loss():
    # one 30C night -> ~14 min debt (no prior debt to recover)
    debt = accumulate_debt([_night(30.0)])
    assert abs(debt - 14.0) < 0.5


def test_consecutive_hot_nights_accumulate():
    one = accumulate_debt([_night(33.0)])
    three = accumulate_debt([_night(33.0), _night(33.0), _night(33.0)])
    assert three > one


def test_cool_night_recovers_debt():
    # hot then cool: debt after cool night is lower than at its peak
    hot_only = accumulate_debt([_night(35.0), _night(35.0)])
    then_cool = accumulate_debt([_night(35.0), _night(35.0), _night(20.0)])
    assert then_cool < hot_only


def test_recovery_never_below_zero():
    nights = [_night(30.0)] + [_night(18.0) for _ in range(10)]
    assert accumulate_debt(nights) == 0.0


def test_debt_capped():
    nights = [_night(50.0) for _ in range(30)]
    assert accumulate_debt(nights) == RECOVERY_DEBT_CAP_MIN


def test_empty_is_zero():
    assert accumulate_debt([]) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/recovery/test_ledger.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prana.recovery.ledger'`

- [ ] **Step 3: Write the module**

Create `prana/recovery/ledger.py`:

```python
"""Chronological sleep-debt ledger.

debt_{n} = clamp(debt_{n-1} + lost_n - recovered_n, 0, CAP)

Recovery is bounded and physical (a cool night clears at most
RECOVERY_PER_COOL_NIGHT_MIN), and a night that itself cost sleep clears
proportionally less debt (you cannot recover on a night you slept badly). This
replaces the old 0.8^days_ago decay and the unitless 100 cap.
"""
from prana.config import RECOVERY_DEBT_CAP_MIN, RECOVERY_PER_COOL_NIGHT_MIN
from prana.recovery.dose_response import minutes_lost


def accumulate_debt(nights) -> float:
    """Walk nights oldest-first, returning final carried debt in minutes.

    nights: list of {'effective_temp', 'humidity', 'hot_climate'} in
            chronological order (oldest first).
    """
    debt = 0.0
    for night in nights:
        lost = minutes_lost(
            night.get('effective_temp'),
            humidity=night.get('humidity'),
            hot_climate=night.get('hot_climate', False),
        )
        # A hot night clears little/no debt; a fully-cool night clears the most.
        # recovery fraction falls to 0 once a night's own loss reaches the
        # per-night recovery budget.
        recovery = max(0.0, RECOVERY_PER_COOL_NIGHT_MIN - lost)
        debt = debt + lost - recovery
        debt = max(0.0, min(RECOVERY_DEBT_CAP_MIN, debt))
    return debt
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/recovery/test_ledger.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add prana/recovery/ledger.py tests/recovery/test_ledger.py
git commit -m "feat(recovery): chronological sleep-debt ledger with bounded recovery"
```

---

### Task 6: Timezone-aware forecast module

**Files:**
- Create: `prana/recovery/forecast.py`
- Test: `tests/recovery/test_forecast.py`

**Interfaces:**
- Produces:
  - `estimate_nighttime_conditions_from_forecast(weather_forecast, now=None) -> Optional[dict]` — `{'temp': float, 'humidity': Optional[float]}` or None. Same selection logic as the legacy method (coldest valid future night hour 22:00-06:00, 6-30h ahead; fallback to coldest of next 8 future hours; discard malformed/stale). `now` is injectable for testing (defaults to `datetime.now()`).
  - `select_night_date(now=None) -> date` — the calendar date the *upcoming* night belongs to (fixes the `datetime.now().date()` bug where a post-midnight run mislabels the night). Injectable `now`.

- [ ] **Step 1: Write the failing test**

Create `tests/recovery/test_forecast.py`:

```python
from datetime import datetime, date, timedelta
from prana.recovery.forecast import (
    estimate_nighttime_conditions_from_forecast,
    select_night_date,
)


def _pt(ts, temp, humidity=None):
    return {"timestamp": ts, "temp": temp, "humidity": humidity}


def test_picks_coldest_future_night_hour():
    now = datetime(2026, 7, 2, 18, 0)
    fc = [
        _pt(now + timedelta(hours=7), 30.0, 60),   # 01:00 next day, night
        _pt(now + timedelta(hours=9), 27.0, 70),   # 03:00, colder night
        _pt(now + timedelta(hours=12), 33.0, 40),  # 06:00
    ]
    out = estimate_nighttime_conditions_from_forecast(fc, now=now)
    assert out["temp"] == 27.0
    assert out["humidity"] == 70


def test_discards_stale_points():
    now = datetime(2026, 7, 2, 18, 0)
    fc = [_pt(now - timedelta(hours=2), 10.0)]  # past
    assert estimate_nighttime_conditions_from_forecast(fc, now=now) is None


def test_skips_malformed_points():
    now = datetime(2026, 7, 2, 18, 0)
    fc = [
        {"timestamp": "not-a-datetime", "temp": 25.0},
        _pt(now + timedelta(hours=8), 26.0, 55),  # 02:00 night
    ]
    out = estimate_nighttime_conditions_from_forecast(fc, now=now)
    assert out["temp"] == 26.0


def test_empty_forecast_none():
    assert estimate_nighttime_conditions_from_forecast([], now=datetime(2026, 7, 2, 18, 0)) is None
    assert estimate_nighttime_conditions_from_forecast(None, now=datetime(2026, 7, 2, 18, 0)) is None


def test_night_date_before_midnight_is_today():
    # 22:00 -> the upcoming night is tonight (today's date)
    assert select_night_date(now=datetime(2026, 7, 2, 22, 0)) == date(2026, 7, 2)


def test_night_date_after_midnight_belongs_to_prior_evening():
    # 02:00 -> still "last night", label it the prior calendar day
    assert select_night_date(now=datetime(2026, 7, 3, 2, 0)) == date(2026, 7, 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/recovery/test_forecast.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prana.recovery.forecast'`

- [ ] **Step 3: Write the module**

Create `prana/recovery/forecast.py`. Port the legacy selection logic verbatim, adding the injectable `now` and the `select_night_date` helper:

```python
"""Timezone-aware nighttime condition selection from a weather forecast.

Selection logic is unchanged from the legacy RDSCalculator method; the two fixes
are (1) an injectable `now` for deterministic tests, and (2) select_night_date,
which labels a post-midnight run with the evening the night began on, fixing the
datetime.now().date() bug that mislabelled early-morning runs.
"""
import math
from datetime import datetime, date, timedelta
from typing import Optional
from backend.logger import get_logger

_log = get_logger("recovery.forecast")


def select_night_date(now=None) -> date:
    """Calendar date the current/upcoming night belongs to.

    A run at 02:00 is still 'last night' -> label it the previous day. A run at or
    after ~18:00 (or any time before midnight) belongs to today.
    """
    if now is None:
        now = datetime.now()
    if now.hour < 12:
        return (now - timedelta(days=1)).date()
    return now.date()


def estimate_nighttime_conditions_from_forecast(weather_forecast, now=None) -> Optional[dict]:
    """Coldest valid future night hour (22:00-06:00, 6-30h ahead) + its humidity.

    Returns {'temp': float, 'humidity': float|None} or None if no valid future
    data. Malformed and stale points are discarded.
    """
    if not weather_forecast:
        return None
    if now is None:
        now = datetime.now()

    valid_items = []
    malformed = 0
    for item in weather_forecast:
        ts = item.get('timestamp')
        temp = item.get('temp')
        if not isinstance(ts, datetime) or temp is None:
            malformed += 1
            continue
        try:
            temp = float(temp)
        except (TypeError, ValueError):
            malformed += 1
            continue
        if not math.isfinite(temp):
            malformed += 1
            continue
        valid_items.append({'timestamp': ts, 'temp': temp, 'humidity': item.get('humidity')})

    if malformed:
        _log.warning("Discarded %d malformed forecast points (bad timestamp or temp)", malformed)
    if not valid_items:
        _log.error("No well-formed forecast points available")
        return None

    night_points = []
    stale_count = 0
    for item in valid_items:
        if item['timestamp'] <= now:
            stale_count += 1
            continue
        time_diff = (item['timestamp'] - now).total_seconds() / 3600
        if 6 <= time_diff <= 30:
            hour = item['timestamp'].hour
            if hour >= 22 or hour <= 6:
                night_points.append((item['timestamp'], item['temp'], item.get('humidity')))

    if stale_count > 0:
        _log.warning("Discarded %d stale forecast points (timestamps in the past)", stale_count)

    if not night_points:
        valid_future = [item for item in valid_items if item['timestamp'] > now]
        if not valid_future:
            _log.error("All forecast timestamps stale - no valid future data available")
            return None
        fallback = valid_future[:8]
        coldest = min(fallback, key=lambda x: x['temp'])
        return {'temp': coldest['temp'], 'humidity': coldest.get('humidity')}

    _, min_temp, min_humidity = min(night_points, key=lambda x: x[1])
    return {'temp': min_temp, 'humidity': min_humidity}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/recovery/test_forecast.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add prana/recovery/forecast.py tests/recovery/test_forecast.py
git commit -m "feat(recovery): tz-aware forecast night selection (fixes now().date() bug)"
```

---

### Task 7: RecoveryModel facade — construction, ingestion, tiers

**Files:**
- Create: `prana/recovery/model.py`
- Modify: `prana/recovery/__init__.py` (export `RecoveryModel`)
- Test: `tests/recovery/test_model_core.py`

**Interfaces:**
- Consumes: all four modules above; `RECOVERY_WINDOW_NIGHTS`, `RECOVERY_TIER_*` from config.
- Produces `RecoveryModel`:
  - `__init__(self, onboarding_data=None)` — holds `self.nighttime_temps = []`, `self.onboarding_data`.
  - staticmethods `compute_onboarding_temp_offset(...)`, `compute_band_width(...)` delegating to `indoor_climate` (preserves the `RecoveryModel.compute_*` call sites in backend/main).
  - `add_night_temperature(self, night_temp, date=None, humidity=None)` — same validation + dedupe-by-date + window trim (to `RECOVERY_WINDOW_NIGHTS`) as legacy; `date` defaults to `select_night_date()`.
  - `classify_tier(self, debt_minutes) -> str` — LOW/MODERATE/HIGH/SEVERE from `RECOVERY_TIER_*`.

- [ ] **Step 1: Write the failing test**

Create `tests/recovery/test_model_core.py`:

```python
import math
from datetime import date
from prana.recovery.model import RecoveryModel


def test_rejects_non_numeric_temp():
    m = RecoveryModel()
    m.add_night_temperature(None, date=date(2026, 7, 1))
    m.add_night_temperature(float("nan"), date=date(2026, 7, 1))
    assert m.nighttime_temps == []


def test_dedupe_by_date_updates_in_place():
    m = RecoveryModel()
    m.add_night_temperature(30.0, date=date(2026, 7, 1))
    m.add_night_temperature(33.0, date=date(2026, 7, 1), humidity=70)
    assert len(m.nighttime_temps) == 1
    assert m.nighttime_temps[0]["temp"] == 33.0
    assert m.nighttime_temps[0]["humidity"] == 70


def test_window_trims_to_config_window():
    from prana.config import RECOVERY_WINDOW_NIGHTS
    m = RecoveryModel()
    for d in range(1, RECOVERY_WINDOW_NIGHTS + 4):
        m.add_night_temperature(30.0, date=date(2026, 7, d))
    assert len(m.nighttime_temps) == RECOVERY_WINDOW_NIGHTS


def test_static_offset_helpers_delegate():
    # backend/main.py calls these as staticmethods
    assert RecoveryModel.compute_onboarding_temp_offset(None) == 0.0
    assert RecoveryModel.compute_band_width({}) > 0


def test_classify_tier():
    m = RecoveryModel()
    assert m.classify_tier(0.0) == "LOW"
    assert m.classify_tier(45.0) == "MODERATE"
    assert m.classify_tier(120.0) == "HIGH"
    assert m.classify_tier(200.0) == "SEVERE"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/recovery/test_model_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prana.recovery.model'`

- [ ] **Step 3: Write the model core**

Create `prana/recovery/model.py`:

```python
"""RecoveryModel: consumer-facing facade over the sleep-debt ledger modules.

Preserves the legacy RDSCalculator entry points so prana_system, ccri_calculator,
backend/main, and ai_tools/checkin migrate with minimal churn, while the internals
are the physical-units ledger.
"""
import math
from datetime import datetime
from prana.config import (
    RECOVERY_WINDOW_NIGHTS,
    RECOVERY_TIER_MODERATE_MIN,
    RECOVERY_TIER_HIGH_MIN,
    RECOVERY_TIER_SEVERE_MIN,
)
from prana.recovery import indoor_climate
from prana.recovery.forecast import select_night_date
from backend.logger import get_logger

_log = get_logger("recovery.model")


class RecoveryModel:
    def __init__(self, onboarding_data=None):
        self.nighttime_temps = []  # list of {'date', 'temp', 'humidity'?}
        self.onboarding_data = onboarding_data

    # --- offset helpers (delegated; preserve legacy staticmethod call sites) ---
    @staticmethod
    def compute_onboarding_temp_offset(onboarding_data, outdoor_temp=None, climate_zone="default"):
        return indoor_climate.compute_onboarding_temp_offset(
            onboarding_data, outdoor_temp=outdoor_temp, climate_zone=climate_zone
        )

    @staticmethod
    def compute_band_width(onboarding_data):
        return indoor_climate.compute_band_width(onboarding_data)

    # --- ingestion ---
    def add_night_temperature(self, night_temp, date=None, humidity=None):
        """Store a night's minimum temperature. Invalid temps are rejected.

        `date` defaults to the correct calendar night via select_night_date().
        """
        try:
            night_temp = float(night_temp)
        except (TypeError, ValueError):
            _log.warning("Ignoring night temperature that is not a number: %r", night_temp)
            return
        if not math.isfinite(night_temp):
            _log.warning("Ignoring non-finite night temperature: %r", night_temp)
            return

        if date is None:
            date = select_night_date()

        existing = [n for n in self.nighttime_temps if n['date'] == date]
        if existing:
            for n in self.nighttime_temps:
                if n['date'] == date:
                    n['temp'] = night_temp
                    if humidity is not None:
                        n['humidity'] = humidity
                    break
        else:
            entry = {'date': date, 'temp': night_temp}
            if humidity is not None:
                entry['humidity'] = humidity
            self.nighttime_temps.append(entry)

        self.nighttime_temps = sorted(
            self.nighttime_temps, key=lambda x: x['date'], reverse=True
        )[:RECOVERY_WINDOW_NIGHTS]

    # --- tiering ---
    def classify_tier(self, debt_minutes) -> str:
        if debt_minutes >= RECOVERY_TIER_SEVERE_MIN:
            return "SEVERE"
        if debt_minutes >= RECOVERY_TIER_HIGH_MIN:
            return "HIGH"
        if debt_minutes >= RECOVERY_TIER_MODERATE_MIN:
            return "MODERATE"
        return "LOW"
```

Update `prana/recovery/__init__.py`:

```python
"""Physically-grounded sleep-debt recovery model (RDS rebuild)."""
from prana.recovery.wetbulb import wet_bulb_stull
from prana.recovery.model import RecoveryModel

__all__ = ["wet_bulb_stull", "RecoveryModel"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/recovery/test_model_core.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add prana/recovery/model.py prana/recovery/__init__.py tests/recovery/test_model_core.py
git commit -m "feat(recovery): RecoveryModel facade (ingestion, tiers, offset delegation)"
```

---

### Task 8: RecoveryModel.calculate_rds — the debt-to-band contract

**Files:**
- Modify: `prana/recovery/model.py`
- Test: `tests/recovery/test_model_calculate.py`

**Interfaces:**
- Consumes: `indoor_climate.compute_onboarding_temp_offset`/`effective_indoor_temp`, `ledger.accumulate_debt`, `RECOVERY_DEBT_CAP_MIN`.
- Produces `calculate_rds(self, debug=False, outdoor_night_temp=None, onboarding_data=None, climate_zone="default", personalized_offset=None, personalized_band=None) -> dict` with keys:
  - **Legacy-compatible (0-100 scale, so ccri/messages keep working):** `rds_low`, `rds_mid`, `rds_high`, `consecutive_nights`, `personalized`.
  - **New:** `debt_minutes_low`, `debt_minutes_mid`, `debt_minutes_high`, `tier`.
  - The 0-100 `rds_*` values are `debt_minutes / RECOVERY_DEBT_CAP_MIN * 100` (so a full 240-min debt = 100). This keeps CRITICAL **reachable by heat alone** — the old defect where only check-ins could exceed 100 is gone because debt is capped at 240 min = 100 on the legacy scale, and check-ins nudge the offset (Task 9) rather than adding raw points.
  - Band: mid uses the resolved offset; low/high shift the per-night offset by `±band_width` before recomputing debt.

- [ ] **Step 1: Write the failing test**

Create `tests/recovery/test_model_calculate.py`:

```python
from datetime import date, timedelta
from prana.recovery.model import RecoveryModel


def _seed(m, temps, start=date(2026, 7, 1)):
    for i, t in enumerate(temps):
        m.add_night_temperature(t, date=start + timedelta(days=i))


def test_empty_returns_zero_dict_with_all_keys():
    m = RecoveryModel()
    out = m.calculate_rds()
    for k in ("rds_low", "rds_mid", "rds_high", "consecutive_nights",
              "personalized", "debt_minutes_mid", "tier"):
        assert k in out
    assert out["rds_mid"] == 0.0
    assert out["debt_minutes_mid"] == 0.0
    assert out["tier"] == "LOW"


def test_cool_history_zero_debt():
    m = RecoveryModel()
    _seed(m, [29, 30, 28, 30])
    out = m.calculate_rds()
    assert out["debt_minutes_mid"] == 0.0
    assert out["rds_mid"] == 0.0


def test_hot_history_accumulates_debt():
    m = RecoveryModel()
    _seed(m, [35, 36, 34])
    out = m.calculate_rds()
    assert out["debt_minutes_mid"] > 0
    assert out["rds_mid"] > 0


def test_band_is_ordered():
    m = RecoveryModel()
    _seed(m, [34, 35, 33])
    out = m.calculate_rds()
    assert out["rds_low"] <= out["rds_mid"] <= out["rds_high"]
    assert out["debt_minutes_low"] <= out["debt_minutes_mid"] <= out["debt_minutes_high"]


def test_rds_scale_capped_at_100_by_debt_cap():
    m = RecoveryModel()
    _seed(m, [50, 50, 50, 50, 50, 50, 50])
    out = m.calculate_rds()
    assert out["rds_mid"] == 100.0  # 240-min cap -> 100
    assert out["debt_minutes_mid"] == 240.0


def test_personalized_offset_used():
    m = RecoveryModel()
    _seed(m, [33, 33, 33])
    warm = m.calculate_rds(personalized_offset=2.0)   # hotter room
    cool = m.calculate_rds(personalized_offset=-5.0)  # much cooler room
    assert warm["debt_minutes_mid"] > cool["debt_minutes_mid"]
    assert warm["personalized"] is True


def test_differentiator_hot_vs_cool_history_same_tonight():
    # The core proof: identical cool tonight, opposite history -> different debt.
    hot = RecoveryModel(); _seed(hot, [35, 36, 34, 30])
    cool = RecoveryModel(); _seed(cool, [29, 28, 29, 30])
    assert hot.calculate_rds()["debt_minutes_mid"] > cool.calculate_rds()["debt_minutes_mid"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/recovery/test_model_calculate.py -v`
Expected: FAIL with `AttributeError: 'RecoveryModel' object has no attribute 'calculate_rds'`

- [ ] **Step 3: Implement calculate_rds and its helpers**

Add to `prana/recovery/model.py` (extend the imports at the top and append methods to the class):

```python
# add to the imports block at the top of model.py:
from prana.config import RECOVERY_DEBT_CAP_MIN
from prana.recovery import ledger
```

```python
    # --- core computation ---
    def _debt_for_offset_shift(self, offset_shift, personalized_offset,
                               onboarding_data, climate_zone):
        """Accumulate debt walking nights oldest-first at a given band shift."""
        onb = onboarding_data or self.onboarding_data
        sorted_nights = sorted(self.nighttime_temps, key=lambda x: x['date'])  # oldest first
        ledger_nights = []
        for night in sorted_nights:
            if personalized_offset is not None:
                offset = float(personalized_offset)
            else:
                offset = indoor_climate.compute_onboarding_temp_offset(
                    onb, outdoor_temp=night['temp'], climate_zone=climate_zone
                )
            offset += offset_shift
            eff = indoor_climate.effective_indoor_temp(night['temp'], offset)
            ledger_nights.append({
                'effective_temp': eff,
                'humidity': night.get('humidity'),
                'hot_climate': False,
            })
        return ledger.accumulate_debt(ledger_nights)

    def _consecutive_impaired_nights(self, personalized_offset, onboarding_data, climate_zone):
        """Count consecutive most-recent nights with non-zero sleep loss."""
        from prana.recovery.dose_response import minutes_lost
        onb = onboarding_data or self.onboarding_data
        sorted_nights = sorted(self.nighttime_temps, key=lambda x: x['date'], reverse=True)
        count = 0
        for night in sorted_nights:
            if personalized_offset is not None:
                offset = float(personalized_offset)
            else:
                offset = indoor_climate.compute_onboarding_temp_offset(
                    onb, outdoor_temp=night['temp'], climate_zone=climate_zone
                )
            eff = indoor_climate.effective_indoor_temp(night['temp'], offset)
            if minutes_lost(eff, humidity=night.get('humidity')) > 0:
                count += 1
            else:
                break
        return count

    def calculate_rds(self, debug=False, outdoor_night_temp=None,
                      onboarding_data=None, climate_zone="default",
                      personalized_offset=None, personalized_band=None):
        """Compute sleep-debt (minutes) with an uncertainty band, plus a
        legacy-compatible 0-100 projection (debt / CAP * 100)."""
        personalized = personalized_offset is not None
        if not self.nighttime_temps:
            return {
                'rds_low': 0.0, 'rds_mid': 0.0, 'rds_high': 0.0,
                'consecutive_nights': 0, 'personalized': personalized,
                'debt_minutes_low': 0.0, 'debt_minutes_mid': 0.0,
                'debt_minutes_high': 0.0, 'tier': 'LOW',
            }

        if personalized_offset is not None:
            band_width = (personalized_band if personalized_band is not None
                          else self.compute_band_width(onboarding_data or self.onboarding_data))
        else:
            band_width = self.compute_band_width(onboarding_data or self.onboarding_data)

        # low = cooler room (more negative offset) -> less debt; high = hotter room.
        debt_mid = self._debt_for_offset_shift(0.0, personalized_offset, onboarding_data, climate_zone)
        debt_low = self._debt_for_offset_shift(-band_width, personalized_offset, onboarding_data, climate_zone)
        debt_high = self._debt_for_offset_shift(+band_width, personalized_offset, onboarding_data, climate_zone)

        consecutive = self._consecutive_impaired_nights(personalized_offset, onboarding_data, climate_zone)

        def to_scale(d):
            return round(min(100.0, d / RECOVERY_DEBT_CAP_MIN * 100.0), 1)

        result = {
            'rds_low': to_scale(debt_low),
            'rds_mid': to_scale(debt_mid),
            'rds_high': to_scale(debt_high),
            'consecutive_nights': consecutive,
            'personalized': personalized,
            'debt_minutes_low': round(debt_low, 1),
            'debt_minutes_mid': round(debt_mid, 1),
            'debt_minutes_high': round(debt_high, 1),
            'tier': self.classify_tier(debt_mid),
        }
        if debug:
            _log.debug("Recovery debt (low/mid/high min): %.1f / %.1f / %.1f | tier=%s",
                       debt_low, debt_mid, debt_high, result['tier'])
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/recovery/test_model_calculate.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add prana/recovery/model.py tests/recovery/test_model_calculate.py
git commit -m "feat(recovery): calculate_rds returns debt-minutes band + legacy 0-100 projection"
```

---

### Task 9: Bounded check-in adjustment + messaging + forecast delegation

**Files:**
- Modify: `prana/recovery/model.py`
- Test: `tests/recovery/test_model_checkin_message.py`

**Interfaces:**
- Consumes: `select_night_date`, `forecast.estimate_nighttime_conditions_from_forecast`.
- Produces on `RecoveryModel`:
  - `apply_sleep_checkin_adjustment(self, rds_dict, checkin=None) -> (dict, dict)` — **bounded**: a check-in shifts debt by at most `±RECOVERY_PER_COOL_NIGHT_MIN` minutes (so a "bad sleep" tap can never out-signal a heatwave, unlike the old flat +20/−10 on the 0-100 scale). Rescales `rds_*` and `debt_minutes_*`, preserves all keys incl. `personalized`, `tier`.
  - `estimate_recovery_confidence(self, checkin=None) -> str` — LOW/MEDIUM/HIGH (same rule as legacy).
  - `get_rds_message(self, rds_dict, outdoor_temp=None) -> (str, str)` — human message in minutes + tier + color.
  - `estimate_nighttime_temp_from_forecast`, `estimate_nighttime_conditions_from_forecast` — delegate to `forecast` module.

- [ ] **Step 1: Write the failing test**

Create `tests/recovery/test_model_checkin_message.py`:

```python
from datetime import date, timedelta
from prana.recovery.model import RecoveryModel
from prana.config import RECOVERY_PER_COOL_NIGHT_MIN


def _hot_model():
    m = RecoveryModel()
    for i, t in enumerate([35, 36, 34]):
        m.add_night_temperature(t, date=date(2026, 7, 1) + timedelta(days=i))
    return m


def test_no_checkin_is_noop():
    m = _hot_model()
    rds = m.calculate_rds()
    out, meta = m.apply_sleep_checkin_adjustment(rds, None)
    assert meta["applied"] is False
    assert out["debt_minutes_mid"] == rds["debt_minutes_mid"]


def test_bad_checkin_bounded_by_one_night_budget():
    m = _hot_model()
    rds = m.calculate_rds()
    out, meta = m.apply_sleep_checkin_adjustment(
        rds, {"sleep_quality": "poor", "power_issue": True, "cooling_issue": True})
    delta = out["debt_minutes_mid"] - rds["debt_minutes_mid"]
    assert 0 < delta <= RECOVERY_PER_COOL_NIGHT_MIN + 1e-6


def test_good_checkin_reduces_debt_not_below_zero():
    m = _hot_model()
    rds = m.calculate_rds()
    out, _ = m.apply_sleep_checkin_adjustment(rds, {"sleep_quality": "good"})
    assert out["debt_minutes_mid"] <= rds["debt_minutes_mid"]
    assert out["debt_minutes_mid"] >= 0.0


def test_checkin_preserves_keys():
    m = _hot_model()
    rds = m.calculate_rds()
    out, _ = m.apply_sleep_checkin_adjustment(rds, {"sleep_quality": "poor"})
    for k in ("rds_mid", "debt_minutes_mid", "tier", "personalized", "consecutive_nights"):
        assert k in out


def test_message_mentions_minutes_and_returns_color():
    m = _hot_model()
    rds = m.calculate_rds()
    msg, color = m.get_rds_message(rds)
    assert "min" in msg.lower()
    assert color in {"GREEN", "YELLOW", "ORANGE", "RED"}


def test_confidence_levels():
    m = RecoveryModel()
    assert m.estimate_recovery_confidence({"sleep_quality": "good"}) == "HIGH"
    assert m.estimate_recovery_confidence() == "LOW"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/recovery/test_model_checkin_message.py -v`
Expected: FAIL with `AttributeError: 'RecoveryModel' object has no attribute 'apply_sleep_checkin_adjustment'`

- [ ] **Step 3: Implement the methods**

Add to the imports in `model.py`:

```python
from prana.config import RECOVERY_PER_COOL_NIGHT_MIN
from prana.recovery import forecast as _forecast
```

Append to the class:

```python
    def apply_sleep_checkin_adjustment(self, rds_dict, checkin=None):
        """Bounded, deterministic check-in nudge (minutes).

        A check-in shifts debt by at most +/- RECOVERY_PER_COOL_NIGHT_MIN, so a
        self-report can refine but never out-signal the weather-driven debt.
        """
        if not checkin:
            return rds_dict, {
                'applied': False, 'delta': 0.0, 'reason': 'no_checkin',
                'adjusted_rds_mid': rds_dict['rds_mid'],
            }

        env = str(checkin.get('sleep_environment', '')).lower()
        quality = str(checkin.get('sleep_quality', '')).lower()
        cooling_issue = bool(checkin.get('cooling_issue', False))
        power_issue = bool(checkin.get('power_issue', False))

        delta = 0.0
        reasons = []
        if env in {'comfortable', 'cool_enough'} or quality == 'good':
            delta -= 20.0
            reasons.append('comfortable_sleep_environment')
        elif env in {'warm_manageable', 'warm'} or quality == 'moderate':
            delta += 8.0
            reasons.append('warm_but_manageable')
        elif env in {'too_hot', 'cooling_unavailable'} or quality == 'poor':
            delta += 25.0
            reasons.append('poor_sleep_environment')
        if cooling_issue:
            delta += 10.0
            reasons.append('cooling_issue')
        if power_issue:
            delta += 15.0
            reasons.append('power_issue')

        # Clamp the total nudge to one night's recovery budget.
        budget = RECOVERY_PER_COOL_NIGHT_MIN
        delta = max(-budget, min(budget, delta))

        def adj(d):
            return max(0.0, min(RECOVERY_DEBT_CAP_MIN, d + delta))

        dmid = adj(rds_dict['debt_minutes_mid'])
        dlow = adj(rds_dict['debt_minutes_low'])
        dhigh = adj(rds_dict['debt_minutes_high'])

        def to_scale(d):
            return round(min(100.0, d / RECOVERY_DEBT_CAP_MIN * 100.0), 1)

        adjusted = {
            'rds_low': to_scale(dlow), 'rds_mid': to_scale(dmid), 'rds_high': to_scale(dhigh),
            'consecutive_nights': rds_dict['consecutive_nights'],
            'personalized': rds_dict.get('personalized', False),
            'debt_minutes_low': round(dlow, 1), 'debt_minutes_mid': round(dmid, 1),
            'debt_minutes_high': round(dhigh, 1),
            'tier': self.classify_tier(dmid),
        }
        return adjusted, {
            'applied': True, 'delta': round(delta, 1),
            'reason': ','.join(reasons) if reasons else 'checkin_no_score_change',
            'adjusted_rds_mid': adjusted['rds_mid'],
            'raw_rds_mid': round(rds_dict['rds_mid'], 1),
        }

    def estimate_recovery_confidence(self, checkin=None):
        if checkin:
            return 'HIGH'
        if len(self.nighttime_temps) >= 3:
            return 'MEDIUM'
        return 'LOW'

    def get_rds_message(self, rds_dict, outdoor_temp=None):
        """Human-readable recovery-debt message (minutes) + color code."""
        if not self.nighttime_temps:
            return "Recovery data unavailable", "UNKNOWN"
        last_temp = self.nighttime_temps[0]['temp'] if self.nighttime_temps else outdoor_temp
        if last_temp is None:
            return "Recovery data unavailable", "UNKNOWN"

        debt = rds_dict['debt_minutes_mid']
        tier = rds_dict.get('tier') or self.classify_tier(debt)
        consecutive = rds_dict['consecutive_nights']
        color = {"LOW": "GREEN", "MODERATE": "YELLOW", "HIGH": "ORANGE", "SEVERE": "RED"}[tier]

        if debt <= 0:
            return (f"Recovery on track (no sleep debt; last night {last_temp:.1f}C)", color)
        band = ""
        if rds_dict['debt_minutes_high'] - rds_dict['debt_minutes_low'] > 15:
            band = f" (range {rds_dict['debt_minutes_low']:.0f}-{rds_dict['debt_minutes_high']:.0f} min)"
        if consecutive >= 3:
            return (f"Recovery debt: ~{debt:.0f} min of sleep lost over {consecutive} hot "
                    f"nights{band} - {tier}", color)
        if consecutive > 0:
            return (f"Recovery debt: ~{debt:.0f} min of lost sleep from {consecutive} hot "
                    f"night(s){band} - {tier}", color)
        return (f"Recovery debt: ~{debt:.0f} min{band} - {tier}", color)

    def estimate_nighttime_temp_from_forecast(self, weather_forecast):
        result = _forecast.estimate_nighttime_conditions_from_forecast(weather_forecast)
        return result['temp'] if result else None

    def estimate_nighttime_conditions_from_forecast(self, weather_forecast):
        return _forecast.estimate_nighttime_conditions_from_forecast(weather_forecast)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/recovery/test_model_checkin_message.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add prana/recovery/model.py tests/recovery/test_model_checkin_message.py
git commit -m "feat(recovery): bounded check-in nudge, minutes-based message, forecast delegation"
```

---

### Task 10: Wire RecoveryModel into ccri_calculator

**Files:**
- Modify: `prana/ccri_calculator.py:60-93`
- Test: `tests/recovery/test_ccri_adapter.py`

**Interfaces:**
- Consumes: the `rds` value passed to CCRI is still the legacy 0-100 `rds_mid` from `calculate_rds` (Task 8 keeps that key), so **CCRI needs no formula change** — but we add an explicit passthrough test and a `to_ccri_recovery_score(debt_minutes)` helper for callers that want to convert raw minutes.
- Produces: `CCRICalculator.to_ccri_recovery_score(debt_minutes) -> float` (0-100). Existing `calculate_recovery_score`/`recovery_score_to_multiplier` unchanged.

- [ ] **Step 1: Write the failing test**

Create `tests/recovery/test_ccri_adapter.py`:

```python
from prana.ccri_calculator import CCRICalculator
from prana.config import RECOVERY_DEBT_CAP_MIN


def test_to_ccri_recovery_score_maps_minutes_to_0_100():
    c = CCRICalculator()
    assert c.to_ccri_recovery_score(0.0) == 0.0
    assert c.to_ccri_recovery_score(RECOVERY_DEBT_CAP_MIN) == 100.0
    assert c.to_ccri_recovery_score(RECOVERY_DEBT_CAP_MIN / 2) == 50.0


def test_existing_recovery_score_still_clamps():
    c = CCRICalculator()
    assert c.calculate_recovery_score(150) == 100
    assert c.calculate_recovery_score(-5) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/recovery/test_ccri_adapter.py -v`
Expected: FAIL with `AttributeError: 'CCRICalculator' object has no attribute 'to_ccri_recovery_score'`

- [ ] **Step 3: Add the adapter**

In `prana/ccri_calculator.py`, add this method immediately after `calculate_recovery_score` (around line 62). Add the import at the top of the file if not present (`from prana.config import RECOVERY_DEBT_CAP_MIN` — verify config import style already used in the file and match it):

```python
    def to_ccri_recovery_score(self, debt_minutes):
        """Map raw sleep-debt minutes to the 0-100 recovery component score.

        A full RECOVERY_DEBT_CAP_MIN of debt maps to 100.
        """
        from prana.config import RECOVERY_DEBT_CAP_MIN
        return max(0.0, min(100.0, debt_minutes / RECOVERY_DEBT_CAP_MIN * 100.0))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/recovery/test_ccri_adapter.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add prana/ccri_calculator.py tests/recovery/test_ccri_adapter.py
git commit -m "feat(ccri): to_ccri_recovery_score adapter for raw debt-minutes"
```

---

### Task 11: Migrate prana_system, backend/main, checkin to RecoveryModel

**Files:**
- Modify: `prana/prana_system.py` (lines 16, 34, and the RDS block ~152-190, backfill ~296-297, seeding ~455-457)
- Modify: `backend/main.py:316,326` (repoint static-method imports)
- Modify: `prana/ai_tools/checkin.py:73` (unchanged call, but the attribute is now a `RecoveryModel`; confirm no rename needed)
- Test: `tests/recovery/test_system_integration.py`

**Interfaces:**
- Consumes: `RecoveryModel` in place of `RDSCalculator`. `self.rds_calculator` attribute name is **kept** (many call sites reference it) — it now holds a `RecoveryModel`.
- Produces: an end-to-end pipeline run that returns the legacy `rds_*` keys plus new `debt_minutes_*`/`tier`.

- [ ] **Step 1: Write the failing test**

Create `tests/recovery/test_system_integration.py`:

```python
from datetime import date, timedelta
from prana.prana_system import PRANASystem


def test_system_uses_recovery_model():
    from prana.recovery.model import RecoveryModel
    sys = PRANASystem(location_name="Chennai")
    assert isinstance(sys.rds_calculator, RecoveryModel)


def test_pipeline_rds_block_returns_debt_keys(monkeypatch):
    sys = PRANASystem(location_name="Chennai")
    # seed a hot history directly on the recovery model
    for i, t in enumerate([35, 36, 34]):
        sys.rds_calculator.add_night_temperature(t, date=date(2026, 7, 1) + timedelta(days=i))
    out = sys.rds_calculator.calculate_rds(climate_zone=sys.climate_zone)
    assert "debt_minutes_mid" in out and "rds_mid" in out and "tier" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/recovery/test_system_integration.py -v`
Expected: FAIL — `test_system_uses_recovery_model` fails because `sys.rds_calculator` is still an `RDSCalculator`.

- [ ] **Step 3: Repoint the consumers**

In `prana/prana_system.py`:
- Line 16, change `from prana.rds_calculator import RDSCalculator` to `from prana.recovery.model import RecoveryModel`.
- Line 34, change `self.rds_calculator = RDSCalculator(onboarding_data)` to `self.rds_calculator = RecoveryModel(onboarding_data)`.
- Verify the RDS block (152-190) still works unchanged: `estimate_nighttime_conditions_from_forecast`, `add_night_temperature`, `calculate_rds`, `apply_sleep_checkin_adjustment`, `get_rds_message` all exist on `RecoveryModel` with the same signatures. No further edits needed there.
- Backfill (296-297) and seeding (455-457): `add_night_temperature(temp, today - timedelta(days=delta))` — these pass explicit dates, so they keep working. No edit needed beyond confirming the import.

In `backend/main.py`:
- Line 316: `from prana.rds_calculator import RDSCalculator` → `from prana.recovery.model import RecoveryModel`, and line 321 `RDSCalculator.compute_onboarding_temp_offset(...)` → `RecoveryModel.compute_onboarding_temp_offset(...)`.
- Line 326: `from prana.rds_calculator import RDSCalculator` → `from prana.recovery.model import RecoveryModel`, and line 327 `RDSCalculator.compute_band_width(...)` → `RecoveryModel.compute_band_width(...)`.

In `prana/ai_tools/checkin.py`:
- Line 73 calls `system.rds_calculator.estimate_nighttime_conditions_from_forecast(forecast)` — the attribute is now a `RecoveryModel` which has this method. No edit needed; confirm by running the checkin tests.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/recovery/test_system_integration.py -v`
Expected: PASS (2 tests)

Then run the broader suite to catch consumer breakage:
Run: `python -m pytest tests/ -x -q`
Expected: The only failures are in the *old* RDS test files (`test_formulas.py`, `test_rds_edge_cases.py`, `test_issue1_rds_bands.py`, `test_personalization.py`) which still import `RDSCalculator` — those are rewritten in Task 12. All other tests PASS. If any non-RDS test fails, stop and fix the wiring before proceeding.

- [ ] **Step 5: Commit**

```bash
git add prana/prana_system.py backend/main.py tests/recovery/test_system_integration.py
git commit -m "feat: wire RecoveryModel into prana_system, backend, checkin"
```

---

### Task 12: Delete old calculator, migrate legacy tests, re-baseline docs & demo

**Files:**
- Delete: `prana/rds_calculator.py`
- Modify/rewrite: `tests/test_formulas.py`, `tests/test_rds_edge_cases.py`, `tests/test_issue1_rds_bands.py`, `tests/test_personalization.py`, `tests/test_issue7_forecast_validation.py`
- Repoint scripts: `scripts/ai_agent_verifier.py`, `scripts/preflight_check.py`, `scripts/test_persistence.py` (imports `RDSCalculator` → `RecoveryModel`)
- Note: `prana/models.py` mentions `RDSCalculator` only in a comment (line 58) — update the comment text, no code change.
- Rewrite: `docs/RDS_MODEL.md`
- Re-baseline: `research/rds_demo/demo.py`, `research/rds_demo/sensitivity.py`, `research/rds_demo/case_study_karachi2015.py` (update imports `RDSCalculator` → `RecoveryModel`; regenerate the printed numbers)

**Interfaces:**
- Consumes: everything above.
- Produces: a green full suite with the old module gone.

- [ ] **Step 1: Find every remaining reference to the old module**

Run: `grep -rn "rds_calculator\|RDSCalculator" prana/ backend/ tests/ research/ scripts/ --include="*.py"`
Expected references (all handled in this task): legacy test files (`test_formulas.py`, `test_rds_edge_cases.py`, `test_issue1_rds_bands.py`, `test_personalization.py`, `test_issue7_forecast_validation.py`), the three `research/rds_demo/` scripts, the three `scripts/` files (`ai_agent_verifier.py`, `preflight_check.py`, `test_persistence.py`), and a comment-only mention in `prana/models.py:58`. Each must be repointed to `prana.recovery.model.RecoveryModel` (or the relevant recovery submodule) or rewritten. `prana_system.py`, `backend/main.py`, `ai_tools/checkin.py` were already migrated in Task 11 — confirm they no longer appear.

- [ ] **Step 2: Rewrite the legacy test files against RecoveryModel**

For each of `tests/test_formulas.py`, `tests/test_rds_edge_cases.py`, `tests/test_issue1_rds_bands.py`, `tests/test_personalization.py`:
- Replace `from prana.rds_calculator import RDSCalculator` (and any `_stull_wet_bulb`, `_rfu_from_excess` imports) with `from prana.recovery.model import RecoveryModel` and `from prana.recovery.wetbulb import wet_bulb_stull`.
- Replace `RDSCalculator(...)` with `RecoveryModel(...)`.
- Assertions keyed to the old score (e.g. "RDS 57.0", "0.8 decay", "RFU 10/degC", the 32C cliff, the `min(100,total)` cap) must be re-expressed against debt-minutes / the new curve. Where an old test asserted an exact legacy number that no longer has meaning, convert it to a **behavioural** assertion (monotonic, ordered band, bounded, silent-when-cool) rather than deleting coverage.
- Delete tests that assert properties the rebuild intentionally removes (the hard `_rfu_from_excess` log tail, the `0.8^days_ago` formula, the flat +20/−10 check-in delta), noting the removal in the commit message.
- `test_personalization.py`: the personalization module calls `compute_onboarding_temp_offset` and infers offsets against `RDS_NIGHTTIME_THRESHOLD`. Confirm `prana/personalization.py` still imports what it needs (it imports from `prana.config`, not `rds_calculator` — verify with grep; if it imports the offset helper from `rds_calculator`, repoint it to `prana.recovery.indoor_climate`).

Run after each file: `python -m pytest tests/<file> -v` until green.

- [ ] **Step 3: Verify personalization still wires correctly**

Run: `grep -n "rds_calculator\|compute_onboarding_temp_offset\|import" prana/personalization.py`
If `personalization.py` references `rds_calculator`, repoint to `prana.recovery.indoor_climate`. Run: `python -m pytest tests/test_personalization.py -v` → PASS.

- [ ] **Step 3b: Repoint the standalone scripts and the models.py comment**

- `scripts/ai_agent_verifier.py`, `scripts/preflight_check.py`, `scripts/test_persistence.py`: replace `from prana.rds_calculator import RDSCalculator` → `from prana.recovery.model import RecoveryModel` and `RDSCalculator(...)` → `RecoveryModel(...)`. Run each script if it's runnable (e.g. `python scripts/preflight_check.py`) or at minimum `python -c "import ast; ast.parse(open('scripts/preflight_check.py').read())"` to confirm it parses; ideally execute to confirm it still works against the new API.
- `prana/models.py:58`: update the comment "reconstruct RDSCalculator" → "reconstruct RecoveryModel". No code change.

- [ ] **Step 4: Delete the old module and confirm nothing imports it**

```bash
git rm prana/rds_calculator.py
```

Run: `grep -rn "rds_calculator\|RDSCalculator" prana/ backend/ tests/ scripts/ --include="*.py"`
Expected: **no matches** (research/ demo scripts handled in Step 6).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: all green (the one pre-existing unrelated South Asia pipeline failure noted in project memory may remain — confirm it is that exact test and unrelated to RDS; everything else PASSES).

- [ ] **Step 6: Re-baseline research/rds_demo and docs**

- In `research/rds_demo/{demo,sensitivity,case_study_karachi2015}.py`: repoint imports to `RecoveryModel`; run each (`python -m research.rds_demo.demo`, `.sensitivity`, `.case_study_karachi2015`) and capture the new printed numbers.
- Rewrite `docs/RDS_MODEL.md`: the model is now minutes-of-sleep-lost, not a unitless score. Update §0-§2 (three-stage computation → indoor_climate / dose_response / ledger), the proof tables (§1) with the regenerated numbers, §2 constants table (new constants from Task 1), and §3 derivation (dose-response now anchored to Minor 2022; recovery is bounded minutes not 0.8 decay). Keep the honesty-tier framing. Mark the compounding tier still-not-outcome-validated.

- [ ] **Step 7: Final full verification + commit**

Run: `python -m pytest -q` → green.
Run: `python -m research.rds_demo.demo` → runs clean, prints the debt-minutes proof.

```bash
git add -A
git commit -m "refactor(recovery): delete rds_calculator, migrate tests & docs to sleep-debt ledger"
```

---

## Self-Review

**1. Spec coverage** (against `project_prana_rds_rebuild.md`):
- Approach A physical-units ledger → Tasks 4, 5, 8. ✓
- Indoor climate reuses `RDS_CLIMATE_ZONE_COEFFS` + ASHRAE AC temp-dependent offset replacing flat −3.0 → Task 1 (constants), Task 3 (module). ✓
- Dose-response anchored to Minor 2022, kills 32C cliff + 10-pts/°C slope → Task 4. ✓
- Debt ledger `clamp(debt + lost − recovery, 0, CAP)`, ~45 min/cool night, cap ~240 → Task 5. ✓
- Bounded check-ins (can't out-signal weather) replacing flat +20/−10 → Task 9. ✓
- tz-aware night selection fixing `datetime.now()` bug → Task 6 (`select_night_date`), Task 7 (default). ✓
- Persistence via existing `RDSState`/database.py → preserved by keeping `nighttime_temps` shape (Global Constraints); Task 11 confirms no migration. ✓
- New structure `prana/recovery/{dose_response,indoor_climate,ledger,forecast}.py` → Tasks 3-6 (+ `wetbulb`, `model` for the facade). ✓
- Rewire prana_system, ccri (`to_ccri_recovery_score`), backend/main, checkin → Tasks 10, 11. ✓
- MOVE `compute_onboarding_temp_offset`/`compute_band_width` preserving semantics → Task 3 (into indoor_climate), Task 7 (re-exposed as `RecoveryModel` staticmethods). ✓
- Delete old rds_calculator.py; rewrite tests + docs + demo → Task 12. ✓
- CRITICAL-tier-unreachable defect → fixed: debt caps at 240 min = 100 on legacy scale, reachable by heat alone; check-ins bounded to one night's budget (Task 8 note, Task 9). ✓
- Proposed constants (`RECOVERY_DEBT_CAP_MIN=240`, `RECOVERY_PER_COOL_NIGHT_MIN=45`, anchors, `RECOVERY_WINDOW_NIGHTS=7`, tiers 30/90/180) → Task 1. ✓ (`IMPAIRED_NIGHT_LOSS_MIN=10` from the memo was dropped — it's implied by the anchor curve, not needed as a separate constant; noted here so it's a conscious omission, not a gap.)

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N" — every code step shows complete code. Task 12's test-migration steps describe *transformations* rather than full rewritten files because the legacy files are large and the transformation rule (repoint imports, convert exact-number asserts to behavioural) is the actual work; each sub-step ends in a concrete `pytest ... -v` gate.

**3. Type consistency:** `minutes_lost(effective_temp, humidity, hot_climate)` used consistently in Tasks 4/5/8. `accumulate_debt(nights)` with `{'effective_temp','humidity','hot_climate'}` dicts consistent Task 5/8. `calculate_rds` dict keys (`rds_*`, `debt_minutes_*`, `consecutive_nights`, `personalized`, `tier`) consistent across Tasks 8/9/11. `compute_onboarding_temp_offset` signature identical to legacy across Tasks 3/7/11. `to_ccri_recovery_score` Task 10 matches its test.

---

## Execution Handoff

Offered after user reviews the plan (below).
