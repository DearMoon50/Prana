"""Wet-bulb temperature via Stull (2011). Moved from rds_calculator, unchanged."""
import math
from typing import Optional


def wet_bulb_stull(temp_c, humidity_percent) -> Optional[float]:
    """Wet-bulb temperature, accurate to ~+/-1C for warm-humid conditions.

    Returns None for unusable inputs (None/NaN/inf, or negative RH). RH above
    100% is clamped to 100% rather than allowed to inflate the estimate.
    """
    if temp_c is None or humidity_percent is None:
        return None
    T = float(temp_c)
    RH = float(humidity_percent)
    if not (math.isfinite(T) and math.isfinite(RH)) or RH < 0:
        return None
    RH = min(RH, 100.0)
    return (
        T * math.atan(0.151977 * math.sqrt(RH + 8.313659))
        + math.atan(T + RH)
        - math.atan(RH - 1.676331)
        + 0.00391838 * (RH ** 1.5) * math.atan(0.023101 * RH)
        - 4.686035
    )
