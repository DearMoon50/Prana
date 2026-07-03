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
    RECOVERY_DEBT_CAP_MIN,
)
from prana.recovery import indoor_climate
from prana.recovery import ledger
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

    # --- core computation ---
    def _debt_for_offset_shift(self, offset_shift, personalized_offset,
                               onboarding_data, climate_zone):
        """Accumulate debt walking nights oldest-first at a given band shift."""
        onb = onboarding_data or self.onboarding_data
        sorted_nights = sorted(self.nighttime_temps, key=lambda x: x['date'])  # oldest first
        ledger_nights = []
        for night in sorted_nights:
            if personalized_offset is not None:
                offset = float(personalized_offset)
            else:
                offset = indoor_climate.compute_onboarding_temp_offset(
                    onb, outdoor_temp=night['temp'], climate_zone=climate_zone
                )
            offset += offset_shift
            eff = indoor_climate.effective_indoor_temp(night['temp'], offset)
            ledger_nights.append({
                'effective_temp': eff,
                'humidity': night.get('humidity'),
                'hot_climate': False,
            })
        return ledger.accumulate_debt(ledger_nights)

    def _consecutive_impaired_nights(self, personalized_offset, onboarding_data, climate_zone):
        """Count consecutive most-recent nights with non-zero sleep loss."""
        from prana.recovery.dose_response import minutes_lost
        onb = onboarding_data or self.onboarding_data
        sorted_nights = sorted(self.nighttime_temps, key=lambda x: x['date'], reverse=True)
        count = 0
        for night in sorted_nights:
            if personalized_offset is not None:
                offset = float(personalized_offset)
            else:
                offset = indoor_climate.compute_onboarding_temp_offset(
                    onb, outdoor_temp=night['temp'], climate_zone=climate_zone
                )
            eff = indoor_climate.effective_indoor_temp(night['temp'], offset)
            if minutes_lost(eff, humidity=night.get('humidity')) > 0:
                count += 1
            else:
                break
        return count

    def calculate_rds(self, debug=False, outdoor_night_temp=None,
                      onboarding_data=None, climate_zone="default",
                      personalized_offset=None, personalized_band=None):
        """Compute sleep-debt (minutes) with an uncertainty band, plus a
        legacy-compatible 0-100 projection (debt / CAP * 100)."""
        personalized = personalized_offset is not None
        if not self.nighttime_temps:
            return {
                'rds_low': 0.0, 'rds_mid': 0.0, 'rds_high': 0.0,
                'consecutive_nights': 0, 'personalized': personalized,
                'debt_minutes_low': 0.0, 'debt_minutes_mid': 0.0,
                'debt_minutes_high': 0.0, 'tier': 'LOW',
            }

        if personalized_offset is not None:
            band_width = (personalized_band if personalized_band is not None
                          else self.compute_band_width(onboarding_data or self.onboarding_data))
        else:
            band_width = self.compute_band_width(onboarding_data or self.onboarding_data)

        # low = cooler room (more negative offset) -> less debt; high = hotter room.
        debt_mid = self._debt_for_offset_shift(0.0, personalized_offset, onboarding_data, climate_zone)
        debt_low = self._debt_for_offset_shift(-band_width, personalized_offset, onboarding_data, climate_zone)
        debt_high = self._debt_for_offset_shift(+band_width, personalized_offset, onboarding_data, climate_zone)

        consecutive = self._consecutive_impaired_nights(personalized_offset, onboarding_data, climate_zone)

        def to_scale(d):
            return round(min(100.0, d / RECOVERY_DEBT_CAP_MIN * 100.0), 1)

        result = {
            'rds_low': to_scale(debt_low),
            'rds_mid': to_scale(debt_mid),
            'rds_high': to_scale(debt_high),
            'consecutive_nights': consecutive,
            'personalized': personalized,
            'debt_minutes_low': round(debt_low, 1),
            'debt_minutes_mid': round(debt_mid, 1),
            'debt_minutes_high': round(debt_high, 1),
            'tier': self.classify_tier(debt_mid),
        }
        if debug:
            _log.debug("Recovery debt (low/mid/high min): %.1f / %.1f / %.1f | tier=%s",
                       debt_low, debt_mid, debt_high, result['tier'])
        return result
