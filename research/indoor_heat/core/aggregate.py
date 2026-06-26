import pandas as pd

def to_logger_nights(df: pd.DataFrame, ts_col: str = "timestamp",
                     logger_col: str = "logger_id", temp_col: str = "temp") -> pd.DataFrame:
    d = df.copy()
    d[ts_col] = pd.to_datetime(d[ts_col])
    hour = d[ts_col].dt.hour
    is_night = (hour >= 22) | (hour <= 6)
    d = d[is_night].copy()
    # Readings at hour <= 6 belong to the previous calendar day's night.
    night_date = d[ts_col].dt.normalize()
    early = d[ts_col].dt.hour <= 6
    night_date = night_date.where(~early, night_date - pd.Timedelta(days=1))
    d["date"] = night_date.dt.date
    g = d.groupby([logger_col, "date"])[temp_col].agg(["min", "mean"]).reset_index()
    g = g.rename(columns={"min": "indoor_night_min", "mean": "indoor_night_mean"})
    return g
