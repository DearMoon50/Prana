import pandas as pd
import numpy as np
import statsmodels.formula.api as smf

def main():
    parquet_path = "data/processed/indoor_heat_merged.parquet"
    df = pd.read_parquet(parquet_path)
    
    # Filter and clean
    d = df.dropna(subset=["indoor_night_min", "outdoor_night_min", "roof_type", "floor_level"]).copy()
    
    FORMULA = "indoor_night_min ~ outdoor_night_min * C(roof_type) + C(floor_level)"
    
    print("Fitting model...")
    model = smf.mixedlm(FORMULA, d, groups=d["site"], re_formula="~outdoor_night_min")
    res = model.fit(method="lbfgs", maxiter=200, disp=False)
    
    print("\n--- MODEL SUMMARY ---")
    print(res.summary())
    
    print("\n--- FIXED EFFECTS ---")
    print(res.fe_params)
    
    print("\n--- RANDOM EFFECTS VARIANCE ---")
    print(res.cov_re)
    
    print("\n--- DATA STATS ---")
    out_temp = d["outdoor_night_min"]
    print(f"outdoor_night_min range: {out_temp.min():.2f} to {out_temp.max():.2f}")
    print(f"outdoor_night_min 5th percentile: {out_temp.quantile(0.05):.2f}")
    print(f"outdoor_night_min 95th percentile: {out_temp.quantile(0.95):.2f}")
    print(f"outdoor_night_min mean: {out_temp.mean():.2f}")
    
    print("\n--- CATEGORIES ---")
    print(f"Roof types present: {d['roof_type'].unique()}")
    print(f"Floor levels present: {d['floor_level'].unique()}")

if __name__ == "__main__":
    main()
