"""Face-validation case study: RDS on the real Karachi June 2015 heatwave.

The Karachi 2015 heatwave killed ~1,200 people. It was a HUMID coastal event —
nights stayed 28-32 C at 77-92% RH, so nighttime recovery failed through the
wet-bulb pathway even though the outdoor dry-bulb minimum rarely crossed 32 C.
That makes it the right test for RDS (a nighttime-recovery model), unlike a dry
inland heatwave whose danger is daytime.

This is FACE VALIDATION, not statistical proof: we show RDS behaves correctly on
a real, documented deadly event for PRANA's target population (a top-floor home
in a dense low-income ward, which runs hotter indoors).

Data: Open-Meteo historical archive (free, no key), hourly 2 m temperature +
relative humidity, nighttime (22:00-06:00) minimum per night. Karachi 24.86N,
67.01E. Embedded below for offline reproducibility; refetch with --refetch.
Source URL:
  https://archive-api.open-meteo.com/v1/archive?latitude=24.86&longitude=67.01
  &start_date=2015-06-16&end_date=2015-06-25
  &hourly=temperature_2m,relative_humidity_2m&timezone=Asia%2FKarachi
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from prana.rds_calculator import RDSCalculator

_REPORT = Path(__file__).parent / "RDS_CASE_STUDY_KARACHI2015.md"

# Real Karachi 2015 nighttime (22:00-06:00) minimums: (label, out_min_C, RH%).
KARACHI_2015 = [
    ("Jun16", 28.2, 89), ("Jun17", 28.5, 86), ("Jun18", 28.7, 87),
    ("Jun19", 29.5, 85), ("Jun20", 30.0, 84), ("Jun21", 30.8, 77),
    ("Jun22", 32.3, 77), ("Jun23", 29.8, 89),
]

# PRANA's target user: top-floor home in a dense low-income ward (hotter indoors).
TARGET_HOME = {"roof_material": "concrete", "floor_level": "top"}


def _naive_verdict(out_min: float) -> str:
    """The baseline RDS competes with: a tonight-only dry-bulb check."""
    return "RISK" if out_min >= 32.0 else "FINE"


def run(nights=KARACHI_2015) -> dict:
    today = date.today()
    calc = RDSCalculator(onboarding_data=TARGET_HOME)
    rows = []
    naive_fine = 0
    for i, (label, out_min, rh) in enumerate(nights):
        # Each night enters the window as the event unfolds.
        calc.add_night_temperature(
            out_min, today - timedelta(days=(len(nights) - 1 - i)), humidity=rh
        )
        r = calc.calculate_rds(climate_zone="hot_humid")
        naive = _naive_verdict(out_min)
        naive_fine += (naive == "FINE")
        rows.append({
            "night": label, "out_min": out_min, "rh": rh, "naive": naive,
            "rds_mid": r["rds_mid"], "tier": calc._classify_rds_tier(r["rds_mid"]),
            "consec": r["consecutive_nights"],
        })
    peak = max(rows, key=lambda x: x["rds_mid"])
    return {"rows": rows, "peak": peak, "naive_fine": naive_fine, "n": len(nights)}


def _report(res: dict) -> str:
    L = [
        "# RDS Case Study — Karachi June 2015 Heatwave (face validation)",
        "",
        "The Karachi 2015 heatwave killed ~1,200 people. It was a **humid coastal** "
        "event: nights stayed hot AND humid, so nighttime recovery failed via the "
        "wet-bulb pathway — exactly what RDS is built to catch. We replay the real "
        "nightly data for PRANA's target user (a **top-floor low-income home**, which "
        "runs hotter indoors).",
        "",
        "Data: Open-Meteo historical archive (hourly 2 m temp + RH, nighttime "
        "22:00-06:00 minimum). This is **face validation on a real event, not "
        "statistical proof.**",
        "",
        "| night | outdoor min | RH | naive dry-bulb (tonight-only) | RDS (mid) | tier |",
        "|---|---|---|---|---|---|",
    ]
    for x in res["rows"]:
        L.append(f"| {x['night']} | {x['out_min']:.1f} °C | {x['rh']}% | "
                 f"{x['naive']} | {x['rds_mid']:.1f} | {x['tier']} |")
    peak = res["peak"]
    L += [
        "",
        "## What this shows",
        "",
        f"- A **naive tonight-only dry-bulb** forecast calls the night **FINE on "
        f"{res['naive_fine']} of {res['n']} nights** — including the last night, when "
        f"RDS has already climbed to its peak.",
        f"- **RDS accumulates recovery debt** across the humid nights, reaching "
        f"**{peak['rds_mid']:.1f} ({peak['tier']})** by {peak['night']} — flagging "
        f"impaired recovery a single-night view misses.",
        "- The signal comes from the **wet-bulb pathway** (high humidity) plus "
        "**multi-night compounding** — RDS's two distinctive mechanisms, on real data.",
        "",
        "## Honest limits",
        "",
        "- Uses outdoor archive data + a **modeled indoor offset** (top-floor home), "
        "not measured bedroom temperature.",
        "- Daily nighttime minimum is a proxy for the sleeping-hours low.",
        "- RDS peaks at MODERATE, not CRITICAL — it is a calibrated, **non-alarmist** "
        "signal, not a mortality predictor. This is face validity, not proof.",
        "",
    ]
    return "\n".join(L)


def main(refetch: bool = False) -> None:
    nights = KARACHI_2015
    if refetch:
        nights = _refetch()
    res = run(nights)
    print(f"{'night':8}{'out-min':>9}{'RH':>5}{'naive':>7}{'RDS_mid':>9}{'tier':>10}")
    for x in res["rows"]:
        print(f"{x['night']:8}{x['out_min']:8.1f}C{x['rh']:>4}%{x['naive']:>7}"
              f"{x['rds_mid']:8.1f} {x['tier']:>9}")
    print(f"\nNaive 'FINE' on {res['naive_fine']}/{res['n']} nights; "
          f"RDS peak {res['peak']['rds_mid']:.1f} ({res['peak']['tier']}).")
    _REPORT.write_text(_report(res), encoding="utf-8")
    print(f"Report written to {_REPORT}")


def _refetch():
    """Re-pull the raw data from Open-Meteo and re-derive nightly minimums."""
    import json
    import urllib.request
    from collections import defaultdict
    from datetime import datetime
    url = ("https://archive-api.open-meteo.com/v1/archive?latitude=24.86&longitude=67.01"
           "&start_date=2015-06-16&end_date=2015-06-25"
           "&hourly=temperature_2m,relative_humidity_2m&timezone=Asia%2FKarachi")
    with urllib.request.urlopen(url, timeout=30) as r:
        d = json.load(r)
    nights = defaultdict(list)
    for t, tp, h in zip(d["hourly"]["time"], d["hourly"]["temperature_2m"],
                        d["hourly"]["relative_humidity_2m"]):
        dt = datetime.fromisoformat(t)
        if dt.hour >= 22 or dt.hour <= 6:
            nights[str(dt.date())].append((tp, h))
    out = []
    for day in sorted(nights)[:8]:
        tp, h = min(nights[day], key=lambda x: x[0])
        out.append((day[5:], round(tp, 1), round(h)))
    return out


if __name__ == "__main__":
    import sys
    main(refetch="--refetch" in sys.argv)
