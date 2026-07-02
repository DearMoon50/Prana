# RDS Suitability Demonstration

Proves RDS is **correct, data-grounded, and differentiated** — suitable to ship
in PRANA (MVP bar, not a full scientific validation). See design spec:
`docs/superpowers/specs/2026-07-02-rds-suitability-demonstration-design.md`.

## Run

```bash
# Full demo (needs the ASHRAE CSV; not committed — it's ~56 MB)
python -m research.rds_demo.demo /path/to/ashrae_db2.01.csv

# Scenario + report only (skips the ASHRAE fit)
python -m research.rds_demo.demo
```

Writes `RDS_DEMO_REPORT.md`. Requires the research extras (`statsmodels`,
`pandas`): `pip install -e .[research]`.

## Data

ASHRAE Global Thermal Comfort Database II (`ashrae_db2.01.csv`, ~107k rows).
Download from the [CBE GitHub](https://github.com/CenterForTheBuiltEnvironment/ashrae-db-II)
or [Dryad](https://datadryad.org/dataset/doi:10.6078/D1F671). **Not committed.**

## Key finding

The AC signal in ASHRAE lives in **office** buildings, not homes (residential
subset has only ~13 air-conditioned rows). So the AC coefficient comes from the
all-buildings fit (office-dominated, labeled): naturally-ventilated runs
**+1.82°C hotter than air-conditioned** at baseline, the gap growing with
outdoor heat — real-data evidence for PRANA's hand-set −3.0°C AC offset (and a
hint that −3.0 is generous for average intermittent AC use).

## Files

- `adapters/ashrae/adapter.py` — maps `ashrae_db2.01.csv` to the canonical
  offset-regression schema (survey data, not time-series; skips the
  `research/indoor_heat/core/` steps).
- `ashrae_offset.py` — residential + all-buildings mixed-effects offset fits.
- `demo.py` — the three-claim demonstration and report generator.
