"""
CCRI RDS Weighting Sensitivity Analysis

Shows the CCRI spread attributable to RDS alone across a range
of heat/pollution/recovery combinations, so we can evaluate
whether the current 0.3 ceiling on recovery_multiplier is appropriate.

Formula:
  base_ccri = (heat_score * pollution_score) / 100
  recovery_multiplier = 1 + (recovery_score / 100) * 0.3
  ccri = base_ccri * recovery_multiplier

Usage:
  python scripts/ccri_rds_sensitivity.py
"""

from prana.ccri_calculator import CCRICalculator

CALC = CCRICalculator()

# Heat score scenarios: LOW (28C), MODERATE (29C), HIGH (31C), VERY HIGH (33C), EXTREME (36C)
HEAT_CASES = [28, 29, 31, 33, 36]

# Pollution scenarios: GOOD (40), MODERATE (80), UNHEALTHY SENS (120), UNHEALTHY (180), HAZARDOUS (250)
POLLUTION_CASES = [40, 80, 120, 180, 250]

# RDS scenarios: 0 (none), 20 (low), 40 (moderate), 60 (high), 80 (very high), 100 (max)
RDS_CASES = [0, 20, 40, 60, 80, 100]

RECOVERY_CEILING = 0.3


def run_sensitivity():
    header = f"{'NDT':>5} | {'HA-AQI':>7} | {'H_scr':>6} | {'P_scr':>7} | {'base':>7} | "
    header += " | ".join(f"RDS={r:<3}" for r in RDS_CASES)
    header += f" | {'RDS spread':>11}"
    sep = "-" * len(header)

    print("=" * len(header))
    print("CCRI SENSITIVITY: RDS INFLUENCE AT 0.3 CEILING")
    print("=" * len(header))
    print()
    print(f"Recovery_multiplier = 1 + (recovery_score / 100) * {RECOVERY_CEILING}")
    print(f"RDS 0   -> multiplier = 1.000  (no contribution)")
    print(f"RDS 100 -> multiplier = {1 + RECOVERY_CEILING:.3f}  (max contribution)")
    print(f"Max CCRI inflation due to RDS: {RECOVERY_CEILING * 100:.0f}%")
    print()

    # Collect all results to find max spread
    all_results = []

    for ndt in HEAT_CASES:
        for ha_aqi in POLLUTION_CASES:
            heat_score = CALC.calculate_heat_score(ndt)
            pollution_score = CALC.calculate_pollution_score(ha_aqi)
            base_ccri = (heat_score * pollution_score) / 100

            row_vals = []
            for rds in RDS_CASES:
                recovery_score = CALC.calculate_recovery_score(rds)
                multiplier = 1 + (recovery_score / 100) * RECOVERY_CEILING
                ccri = base_ccri * multiplier
                row_vals.append(ccri)

            spread = row_vals[-1] - row_vals[0]
            all_results.append((heat_score, pollution_score, base_ccri, row_vals, spread, ndt, ha_aqi))

    # Sort by spread descending, show top 20
    all_results.sort(key=lambda r: r[4], reverse=True)

    print(header)
    print(sep)
    for heat_score, pollution_score, base_ccri, row_vals, spread, ndt, ha_aqi in all_results:
        cells = " | ".join(f"{v:>7.1f}" for v in row_vals)
        print(f"{ndt:>5} | {ha_aqi:>7} | {heat_score:>6.1f} | {pollution_score:>7.1f} | {base_ccri:>7.1f} | {cells} | {spread:>8.1f}")

    print(sep)
    print()

    # Summary statistics
    spreads = [r[4] for r in all_results]
    print(f"Summary across {len(all_results)} combinations:")
    print(f"  Average RDS spread:          {sum(spreads) / len(spreads):.1f} CCRI points")
    print(f"  Min RDS spread:              {min(spreads):.1f} CCRI points")
    print(f"  Max RDS spread:              {max(spreads):.1f} CCRI points")
    print()
    print(f"  At current 0.3 ceiling, even a maximally accurate RDS can move")
    print(f"  the final CCRI by at most {RECOVERY_CEILING * 100:.0f}% of the base_ccri.")
    print(f"  For a moderate day (H={heat_score:.0f}, P={pollution_score:.0f}, base={base_ccri:.0f}),")
    print(f"  the max RDS swing is {spread:.1f} points — which may or may not")
    print(f"  be enough to change a risk tier.")
    print()

    # Quick tier-change analysis
    TIERS = [(20, "SAFE"), (40, "ELEVATED"), (60, "HIGH"), (80, "CRITICAL"), (float('inf'), "EMERGENCY")]
    tier_changes = 0
    total = 0
    for _, _, base_ccri, row_vals, _, _, _ in all_results:
        start_tier = next(t[1] for t in TIERS if base_ccri * 1.0 < t[0])
        end_tier = next(t[1] for t in TIERS if base_ccri * 1.3 < t[0])
        if start_tier != end_tier:
            tier_changes += 1
        total += 1
    print(f"Tier changes attributable to RDS (0->100): {tier_changes}/{total} "
          f"({100 * tier_changes / total:.1f}% of scenarios)")
    print("(A tier change means RDS=100 pushes CCRI into a higher risk tier vs RDS=0)")


if __name__ == "__main__":
    run_sensitivity()
