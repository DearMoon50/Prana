import pandas as pd
from datetime import datetime
from research.indoor_heat.core import outliers, aggregate

def test_filter_indoor_removes_out_of_range():
    df = pd.DataFrame({"temp": [10.0, 30.0, 79.0, 25.0]})
    out, frac = outliers.filter_indoor(df, temp_col="temp")
    assert list(out["temp"]) == [30.0, 25.0]
    assert abs(frac - 0.5) < 1e-9

def test_night_keying_cross_midnight():
    # 23:00 on Mar 1 and 02:00 on Mar 2 belong to the SAME night (Mar 1)
    rows = [
        {"logger_id": "L1", "timestamp": datetime(2016,3,1,23,0), "temp": 33.0},
        {"logger_id": "L1", "timestamp": datetime(2016,3,2,2,0),  "temp": 31.0},
        {"logger_id": "L1", "timestamp": datetime(2016,3,2,14,0), "temp": 40.0},  # daytime, excluded
    ]
    df = pd.DataFrame(rows)
    out = aggregate.to_logger_nights(df)
    assert len(out) == 1
    r = out.iloc[0]
    assert str(r["date"]) == "2016-03-01"
    assert r["indoor_night_min"] == 31.0
    assert abs(r["indoor_night_mean"] - 32.0) < 1e-9
