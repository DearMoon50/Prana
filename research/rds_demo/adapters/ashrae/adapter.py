"""ASHRAE Global Thermal Comfort Database II adapter.

Unlike the South Asia loggers (raw 10-min time series), ASHRAE DB II is a
pre-aggregated *survey* dataset: one row = one occupant's right-here-right-now
comfort observation, with measured indoor air temp and a monthly-mean outdoor
temp. So this adapter does NOT reuse the time-series `core/` steps; it maps the
raw CSV straight to a canonical analysis table for the offset regression.

Honesty boundaries baked into the output labels (see design spec):
  - outdoor temp is a MONTHLY MEAN, not a nightly minimum;
  - observations are DAYTIME comfort votes, not sleep recovery;
  - the dataset is OFFICE-HEAVY, so the residential subset is the headline.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# Raw ASHRAE column -> canonical name. Verified against ashrae_db2.01.csv.
_COLMAP = {
    "Air temperature (C)": "indoor_temp",
    "Outdoor monthly air temperature (C)": "outdoor_temp",
    "Cooling startegy_building level": "cooling_strategy",
    "Koppen climate classification": "climate_zone",
    "Building type": "building_type",
    "Country": "country",
    "Fan": "fan",
    "Window": "window",
    "Relative humidity (%)": "humidity",
    "Thermal sensation": "tsv",
}

# ASHRAE building types that count as residential (homes ~ PRANA's target).
_RESIDENTIAL = {"multifamily housing"}

# Canonical cooling-strategy labels (lowercased raw -> canonical).
_COOLING_CANON = {
    "air conditioned": "air_conditioned",
    "naturally ventilated": "naturally_ventilated",
    "mixed mode": "mixed_mode",
    "mechanically ventilated": "mechanically_ventilated",
}


def _to_bool(series: pd.Series) -> pd.Series:
    """Coerce ASHRAE Fan/Window ('Yes'/'No'/blank) to True/False/NaN."""
    m = series.astype(str).str.strip().str.lower()
    return m.map({"yes": True, "1": True, "true": True,
                  "no": False, "0": False, "false": False})


def load(csv_path: str | Path, residential_only: bool = True) -> pd.DataFrame:
    """Load ASHRAE DB II into the canonical offset-regression schema.

    Args:
        csv_path: path to ashrae_db2.01.csv.
        residential_only: keep only Multifamily housing rows (the headline
            subset). Set False for the all-buildings sensitivity check.

    Returns:
        DataFrame with columns: indoor_temp, outdoor_temp, cooling_strategy,
        climate_zone, building_type, country, fan, window, humidity, tsv.
    """
    raw = pd.read_csv(csv_path, usecols=list(_COLMAP), low_memory=False)
    df = raw.rename(columns=_COLMAP)

    df["cooling_strategy"] = (
        df["cooling_strategy"].astype(str).str.strip().str.lower().map(_COOLING_CANON)
    )
    df["building_type_norm"] = df["building_type"].astype(str).str.strip().str.lower()
    df["fan"] = _to_bool(df["fan"])
    df["window"] = _to_bool(df["window"])

    for col in ("indoor_temp", "outdoor_temp", "humidity", "tsv"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Plausibility filter on indoor temp (mirrors South Asia's 15-50C band).
    df = df[(df["indoor_temp"].between(10, 45)) | df["indoor_temp"].isna()]

    if residential_only:
        df = df[df["building_type_norm"].isin(_RESIDENTIAL)]

    return df.reset_index(drop=True)
