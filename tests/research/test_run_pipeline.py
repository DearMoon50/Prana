import pandas as pd
from pathlib import Path
from research.indoor_heat import run_pipeline
from research.indoor_heat.adapters.south_asia.adapter import SouthAsiaAdapter

def _write_min_site(raw: Path):
    # Indoor: wide format, one logger column, two night readings
    (raw).mkdir(parents=True, exist_ok=True)
    (raw / "Delhi Indoor Data.csv").write_text(
        "Timestamp,L1\n"
        "01-03-2016 23:00,33.0\n"
        "02-03-2016 02:00,31.0\n"
    )
    (raw / "Delhi AWS Data.csv").write_text(
        "Date,Time,Temp Out\n"
        "03-01-2016,11:00 PM,28.0\n"   # AWS dash = MM-DD -> March 1
        "03-02-2016,2:00 AM,27.0\n"
    )
    (raw / "Delhi Housing Structure Data.csv").write_text(
        "Logger ID,Roof,Floor on top\n"
        "L1,Tin,Yes\n"
    )

def test_run_site_produces_canonical_rows(tmp_path):
    raw = tmp_path / "raw"
    _write_min_site(raw)
    adapter = SouthAsiaAdapter(raw_dir=raw)
    df = run_pipeline.run_site(adapter, "delhi")
    assert len(df) == 1
    r = df.iloc[0]
    assert r["roof_type"] == "tin"
    assert r["floor_level"] == "top"
    assert r["indoor_night_min"] == 31.0
