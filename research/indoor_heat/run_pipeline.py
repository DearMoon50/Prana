from __future__ import annotations
"""Wire adapter + core steps into per-site and merged datasets."""
from pathlib import Path
import pandas as pd

from research.indoor_heat.core import outliers, aggregate, dates, harmonize, join, validate, merge
from research.indoor_heat.adapters.south_asia.adapter import SouthAsiaAdapter

def _melt_indoor(raw: pd.DataFrame) -> pd.DataFrame:
    """Wide indoor (timestamp + logger columns) -> long [timestamp, logger_id, temp].
    Drops logger columns suffixed '(RH)' (humidity)."""
    ts_col = raw.columns[0]
    logger_cols = [c for c in raw.columns[1:] if not str(c).strip().endswith("(RH)")]
    long = raw.melt(id_vars=[ts_col], value_vars=logger_cols,
                    var_name="logger_id", value_name="temp")
    long = long.rename(columns={ts_col: "raw_ts"})
    long["temp"] = pd.to_numeric(long["temp"], errors="coerce")
    return long.dropna(subset=["temp"])

def run_site(adapter, site: str) -> pd.DataFrame:
    # --- Indoor ---
    raw_indoor = pd.read_csv(adapter.indoor_path(site))
    long = _melt_indoor(raw_indoor)
    long["timestamp"] = dates.parse_with_continuity(
        long["raw_ts"], dash_is_dmy=adapter.indoor_dash_is_dmy, expected_gap="10min"
    ) if long["raw_ts"].nunique() > 2 else pd.to_datetime(long["raw_ts"], dayfirst=adapter.indoor_dash_is_dmy)
    long, _frac = outliers.filter_indoor(long, temp_col="temp")
    nights = aggregate.to_logger_nights(long)

    # --- AWS (outdoor) ---
    raw_aws = adapter.repair_rows(pd.read_csv(adapter.aws_path(site)), kind="aws")
    raw_aws = raw_aws.rename(columns=adapter.column_map(site))
    date_col, time_col = raw_aws.columns[0], raw_aws.columns[1]
    combined = raw_aws[date_col].astype(str) + " " + raw_aws[time_col].astype(str)
    raw_aws["timestamp"] = pd.to_datetime(combined, dayfirst=adapter.aws_dash_is_dmy, errors="coerce")
    raw_aws = raw_aws.dropna(subset=["timestamp"])
    raw_aws["outdoor_temp"] = pd.to_numeric(raw_aws["outdoor_temp"], errors="coerce")
    aws_nights = aggregate.to_logger_nights(
        raw_aws.assign(logger_id="_aws"), temp_col="outdoor_temp"
    ).rename(columns={"indoor_night_min": "outdoor_night_min",
                      "indoor_night_mean": "outdoor_night_mean"})[
        ["date", "outdoor_night_min", "outdoor_night_mean"]]
    nights = nights.merge(aws_nights, on="date", how="left")

    # --- Housing ---
    housing = pd.read_csv(adapter.housing_path(site))
    hc = housing.columns
    logger_col = next(c for c in hc if "logger" in c.lower() or c.lower() == "id")
    roof_col = next((c for c in hc if "roof" in c.lower()), None)
    floor_col = next((c for c in hc if "floor" in c.lower() or "top" in c.lower()), None)
    housing = housing.rename(columns={logger_col: "logger_id"})
    housing["roof_type"] = harmonize.canonicalize_roof(housing[roof_col], adapter.roof_map(site)) if roof_col else None
    housing["floor_level"] = harmonize.canonicalize_floor(housing[floor_col], adapter.floor_map(site)) if floor_col else "other"
    housing = housing[["logger_id", "roof_type", "floor_level"]]

    df = join.attach_housing(nights, housing)
    df["site"] = site
    df = df[["site", "logger_id", "date", "indoor_night_min", "indoor_night_mean",
             "outdoor_night_min", "outdoor_night_mean", "roof_type", "floor_level"]]
    return df

def run_all(adapter=None, out_path: str | Path = "data/processed/indoor_heat_merged.parquet") -> pd.DataFrame:
    adapter = adapter or SouthAsiaAdapter()
    frames = {}
    for site in adapter.site_names:
        try:
            frames[site] = run_site(adapter, site)
        except FileNotFoundError as e:
            print(f"[skip] {site}: {e}")
    merged = merge.concat_sites(frames) if frames else pd.DataFrame()
    if not merged.empty:
        validate.check_canonical(merged)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        merged.to_parquet(out_path, index=False)
        print(f"Wrote {len(merged)} logger-nights from {len(frames)} sites -> {out_path}")
    return merged

if __name__ == "__main__":
    run_all()
