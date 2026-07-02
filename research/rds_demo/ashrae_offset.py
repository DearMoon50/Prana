"""Fit the indoor-offset model on ASHRAE DB II and report the cooling-strategy
offsets by climate zone.

Two models, because the residential subset (PRANA's target) has almost no
air-conditioned rows (the AC signal lives in offices):

  RESIDENTIAL  -> naturally-ventilated vs mixed-mode offset in homes.
  ALL BUILDINGS -> the AC coefficient (office-dominated; labeled as such).

Mixed-effects: indoor_temp ~ outdoor_temp * cooling_strategy, random intercept
+ outdoor slope grouped by climate_zone. Reports R2(marginal)/RMSE using the
same logic as research/indoor_heat/regression.py so results are comparable.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from research.rds_demo.adapters.ashrae.adapter import load

FORMULA = "indoor_temp ~ outdoor_temp * C(cooling_strategy)"
_FIT_COLS = ["indoor_temp", "outdoor_temp", "cooling_strategy", "climate_zone"]


def fit(df: pd.DataFrame) -> dict:
    """Fit the cooling-strategy offset model; return params, R2, RMSE, n."""
    d = df.dropna(subset=_FIT_COLS).copy()
    # Drop cooling strategies too sparse to estimate (<30 rows) so the design
    # matrix stays well-conditioned.
    keep = d["cooling_strategy"].value_counts()
    d = d[d["cooling_strategy"].isin(keep[keep >= 30].index)]
    model = smf.mixedlm(FORMULA, d, groups=d["climate_zone"],
                        re_formula="~outdoor_temp")
    res = model.fit(method="lbfgs", maxiter=300, disp=False)
    pred = res.fittedvalues
    resid = d["indoor_temp"].values - pred.values
    rmse = float(np.sqrt(np.mean(resid**2)))
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((d["indoor_temp"] - d["indoor_temp"].mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")
    return {
        "params": dict(res.fe_params),
        "conf_int": res.conf_int().to_dict("index"),
        "r2_marginal": r2,
        "rmse": rmse,
        "n": len(d),
        "n_zones": d["climate_zone"].nunique(),
    }


def _print_fit(title: str, out: dict) -> None:
    print(f"\n== {title} ==")
    print(f"n={out['n']}  zones={out['n_zones']}  "
          f"R2(marginal)={out['r2_marginal']:.3f}  RMSE={out['rmse']:.2f}degC")
    print("Fixed effects (offset vs air_conditioned reference):")
    for k, v in out["params"].items():
        lo, hi = out["conf_int"].get(k, (float("nan"), float("nan"))).values() \
            if isinstance(out["conf_int"].get(k), dict) else (float("nan"), float("nan"))
        print(f"  {k:48s} {v:+.4f}  [{lo:+.3f}, {hi:+.3f}]")


def run(csv_path: str) -> dict:
    """Fit residential and all-buildings models; print and return both."""
    res_df = load(csv_path, residential_only=True)
    all_df = load(csv_path, residential_only=False)

    residential = fit(res_df)
    all_bld = fit(all_df)

    _print_fit("RESIDENTIAL (homes; NV vs mixed-mode)", residential)
    _print_fit("ALL BUILDINGS (AC coefficient; office-dominated)", all_bld)

    print("\nCaveats: outdoor temp is a MONTHLY MEAN (not nightly min); "
          "observations are DAYTIME comfort votes (not sleep recovery); "
          "residential AC rows are too few, so the AC number comes from the "
          "office-heavy all-buildings fit.")
    return {"residential": residential, "all_buildings": all_bld}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m research.rds_demo.ashrae_offset <ashrae_db2.01.csv>")
    run(sys.argv[1])
