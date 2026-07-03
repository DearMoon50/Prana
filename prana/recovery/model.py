"""RecoveryModel: consumer-facing facade over the sleep-debt ledger modules.

Preserves the legacy RDSCalculator entry points so prana_system, ccri_calculator,
backend/main, and ai_tools/checkin migrate with minimal churn, while the internals
are the physical-units ledger.
"""
import math
from datetime import datetime
from prana.config import (
    RECOVERY_WINDOW_NIGHTS,
    RECOVERY_TIER_MODERATE_MIN,
    RECOVERY_TIER_HIGH_MIN,
    RECOVERY_TIER_SEVERE_MIN,
)
from prana.recovery import indoor_climate
from prana.recovery.forecast import select_night_date
from backend.logger import get_logger

_log = get_logger("recovery.model")


class RecoveryModel:
    def __init__(self, onboarding_data=None):
        self.nighttime_temps = []  # list of {'date', 'temp', 'humidity'?}
        self.onboarding_data = onboarding_data

    # --- offset helpers (delegated; preserve legacy staticmethod call sites) ---
    @staticmethod
    def compute_onboarding_temp_offset(onboarding_data, outdoor_temp=None, climate_zone="default"):
        return indoor_climate.compute_onboarding_temp_offset(
            onboarding_data, outdoor_temp=outdoor_temp, climate_zone=climate_zone
        )

    @staticmethod
    def compute_band_width(onboarding_data):
        return indoor_climate.compute_band_width(onboarding_data)

    # --- ingestion ---
    def add_night_temperature(self, night_temp, date=None, humidity=None):
        """Store a night's minimum temperature. Invalid temps are rejected.

        `date` defaults to the correct calendar night via select_night_date().
        """
        try:
            night_temp = float(night_temp)
        except (TypeError, ValueError):
            _log.warning("Ignoring night temperature that is not a number: %r", night_temp)
            return
        if not math.isfinite(night_temp):
            _log.warning("Ignoring non-finite night temperature: %r", night_temp)
            return

        if date is None:
            date = select_night_date()

        existing = [n for n in self.nighttime_temps if n['date'] == date]
        if existing:
            for n in self.nighttime_temps:
                if n['date'] == date:
                    n['temp'] = night_temp
                    if humidity is not None:
                        n['humidity'] = humidity
                    break
        else:
            entry = {'date': date, 'temp': night_temp}
            if humidity is not None:
                entry['humidity'] = humidity
            self.nighttime_temps.append(entry)

        self.nighttime_temps = sorted(
            self.nighttime_temps, key=lambda x: x['date'], reverse=True
        )[:RECOVERY_WINDOW_NIGHTS]

    # --- tiering ---
    def classify_tier(self, debt_minutes) -> str:
        if debt_minutes >= RECOVERY_TIER_SEVERE_MIN:
            return "SEVERE"
        if debt_minutes >= RECOVERY_TIER_HIGH_MIN:
            return "HIGH"
        if debt_minutes >= RECOVERY_TIER_MODERATE_MIN:
            return "MODERATE"
        return "LOW"
