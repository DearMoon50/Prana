import pandas as pd

def filter_indoor(df: pd.DataFrame, temp_col: str = "temp",
                  lo: float = 15.0, hi: float = 50.0) -> tuple[pd.DataFrame, float]:
    n0 = len(df)
    keep = df[(df[temp_col] >= lo) & (df[temp_col] <= hi)].copy()
    frac_removed = (n0 - len(keep)) / n0 if n0 else 0.0
    return keep, frac_removed
