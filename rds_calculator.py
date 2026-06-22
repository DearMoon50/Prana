"""Calculate Recovery Debt Score (RDS) based on nighttime temperatures"""
from datetime import datetime
from config import *

class RDSCalculator:
    def __init__(self, onboarding_data=None):
        self.nighttime_temps = []  # Store last 7 nights
        self.onboarding_data = onboarding_data  # Optional dict with ac, roof_material, floor_level

    @staticmethod
    def compute_onboarding_temp_offset(onboarding_data):
        """
        Compute effective indoor temperature offset from onboarding categorical inputs.

        Offsets are applied to outdoor nighttime temp before RFU threshold check.
        All values are PROTOTYPE_ASSUMPTION — not empirically validated.

        Args:
            onboarding_data: dict with keys 'ac' (bool), 'roof_material' (str),
                             'floor_level' (str), or None.

        Returns:
            float: total temperature offset in degC (negative = cooler, positive = hotter).
        """
        if not onboarding_data:
            return 0.0
        offset = 0.0
        if onboarding_data.get('ac'):
            offset += RDS_ONBOARDING_AC_OFFSET
        roof = onboarding_data.get('roof_material', '').lower()
        if roof == 'tin':
            offset += RDS_ONBOARDING_TIN_ROOF_OFFSET
        floor = onboarding_data.get('floor_level', '').lower()
        if floor == 'top':
            offset += RDS_ONBOARDING_TOP_FLOOR_OFFSET
        return round(offset, 1)
    
    def add_night_temperature(self, night_temp, date=None):
        """
        Add a night's minimum temperature to tracking
        
        Args:
            night_temp: Minimum temperature during night (C)
            date: Date of the night (defaults to today)
        """
        if date is None:
            date = datetime.now().date()
        
        # Check if this date already exists
        existing = [n for n in self.nighttime_temps if n['date'] == date]
        if existing:
            for n in self.nighttime_temps:
                if n['date'] == date:
                    n['temp'] = night_temp
                    break
        else:
            self.nighttime_temps.append({
                'date': date,
                'temp': night_temp
            })
        
        # Keep only last 7 nights
        self.nighttime_temps = sorted(self.nighttime_temps, key=lambda x: x['date'], reverse=True)[:RDS_MAX_DAYS]
    
    def calculate_recovery_factor(self, night_temp, indoor_offset=0.0):
        """
        Calculate recovery factor for a single night

        RFU (Recovery Failure Units):
        - Below 32C (effective): RFU = 0 (full recovery possible)
        - Above 32C (effective): RFU increases linearly

        Based on Obradovich et al. (2017):
        Every 10C rise increases sleep insufficiency by 20.1%

        Args:
            night_temp: Nighttime outdoor temperature (C)
            indoor_offset: Effective indoor temperature offset (degC).
                           Positive = hotter indoors, Negative = cooler indoors.

        Returns:
            Recovery Failure Units (0-100)
        """
        effective_temp = night_temp + indoor_offset
        if effective_temp < RDS_NIGHTTIME_THRESHOLD:
            return 0.0

        temp_excess = effective_temp - RDS_NIGHTTIME_THRESHOLD
        rfu = min(100, (temp_excess / 10) * 100)

        return rfu
    
    def calculate_rds(self, debug=False, onboarding_data=None):
        """
        Calculate cumulative Recovery Debt Score

        RDS = sum(RFU x 0.8^days_ago)

        Recent nights weighted more heavily, exponential decay for older nights

        Args:
            debug: If True, print per-night breakdown
            onboarding_data: Optional dict with 'ac', 'roof_material', 'floor_level'
                             for effective indoor temperature adjustment.

        Returns:
            RDS value (0-100+) and number of consecutive nights without recovery
        """
        if not self.nighttime_temps:
            return 0.0, 0

        indoor_offset = self.compute_onboarding_temp_offset(onboarding_data or self.onboarding_data)
        total_rds = 0.0
        consecutive_nights = 0
        first_hot_night_days_ago = -1
        today = datetime.now().date()

        if debug:
            print(f"\n  RDS Calculation Breakdown:")
            print(f"  {'Date':<12} {'Temp':<8} {'Offset':<8} {'Eff Temp':<9} {'RFU':<8} {'Days Ago':<10} {'Weight':<10} {'Contribution':<12}")
            print(f"  {'-'*90}")

        sorted_nights = sorted(self.nighttime_temps, key=lambda x: x['date'], reverse=True)
        for i, night in enumerate(sorted_nights):
            days_ago = (today - night['date']).days
            effective_temp = night['temp'] + indoor_offset
            rfu = self.calculate_recovery_factor(night['temp'], indoor_offset)
            weight = RDS_DECAY_FACTOR ** days_ago
            contribution = rfu * weight
            total_rds += contribution
            if debug:
                date_str = night['date'].strftime('%Y-%m-%d')
                if days_ago == 0:
                    date_str += " (tonight)"
                print(f"  {date_str:<12} {night['temp']:.1f}C  {indoor_offset:>+7.1f}  {effective_temp:>7.1f}C  {rfu:>6.1f}  {days_ago:>9}  {weight:>9.3f}  {contribution:>11.1f}")
            if effective_temp >= RDS_NIGHTTIME_THRESHOLD:
                if consecutive_nights == 0:
                    consecutive_nights = 1
                    first_hot_night_days_ago = days_ago
                elif days_ago == first_hot_night_days_ago + consecutive_nights:
                    consecutive_nights += 1

        if debug:
            print(f"  {'-'*90}")
            print(f"  Indoor offset applied: {indoor_offset:+.1f}C")
            print(f"  Total RDS: {total_rds:.1f}")
            print(f"  Consecutive nights (effective >=32C): {consecutive_nights}\n")
        return total_rds, consecutive_nights

    def apply_sleep_checkin_adjustment(self, rds, checkin=None):
        """
        Adjust RDS with structured user-reported sleep environment data.

        This is deterministic and capped. The LLM may extract `checkin`, but it
        should not decide the score.
        """
        if not checkin:
            return rds, {
                'applied': False,
                'delta': 0.0,
                'reason': 'no_checkin',
                'adjusted_rds': rds,
            }

        sleep_environment = str(checkin.get('sleep_environment', '')).lower()
        sleep_quality = str(checkin.get('sleep_quality', '')).lower()
        cooling_issue = bool(checkin.get('cooling_issue', False))
        power_issue = bool(checkin.get('power_issue', False))

        delta = 0.0
        reasons = []

        if sleep_environment in {'comfortable', 'cool_enough'} or sleep_quality == 'good':
            delta -= 10.0
            reasons.append('comfortable_sleep_environment')
        elif sleep_environment in {'warm_manageable', 'warm'} or sleep_quality == 'moderate':
            delta += 5.0
            reasons.append('warm_but_manageable')
        elif sleep_environment in {'too_hot', 'cooling_unavailable'} or sleep_quality == 'poor':
            delta += 20.0
            reasons.append('poor_sleep_environment')

        if cooling_issue:
            delta += 10.0
            reasons.append('cooling_issue')
        if power_issue:
            delta += 15.0
            reasons.append('power_issue')

        adjusted_rds = max(0.0, min(200.0, rds + delta))
        return adjusted_rds, {
            'applied': True,
            'delta': round(adjusted_rds - rds, 1),
            'reason': ','.join(reasons) if reasons else 'checkin_no_score_change',
            'adjusted_rds': round(adjusted_rds, 1),
            'raw_rds': round(rds, 1),
        }

    def estimate_recovery_confidence(self, checkin=None):
        if checkin:
            return 'HIGH'
        if len(self.nighttime_temps) >= 3:
            return 'MEDIUM'
        return 'LOW'
    
    def get_rds_message(self, outdoor_temp=None):
        """
        Get human-readable recovery debt message as a range

        Since we don't know indoor temperature, we output RDS as a range based on outdoor temp.

        Args:
            outdoor_temp: Last night's outdoor minimum temperature (C)

        Returns:
            Tuple of (message, color_code)
        """
        rds, consecutive_nights = self.calculate_rds(onboarding_data=self.onboarding_data)
        
        if not self.nighttime_temps:
            return "Recovery data unavailable", "UNKNOWN"
        
        # Get the most recent night temperature
        last_night_temp = self.nighttime_temps[0]['temp'] if self.nighttime_temps else outdoor_temp
        
        if last_night_temp is None:
            return "Recovery data unavailable", "UNKNOWN"
        
        # Generate range-based message using BOTH rds score AND outdoor temp
        # RDS scale: 0-30 = LOW, 30-60 = MODERATE, 60-100 = HIGH, 100-150 = VERY HIGH, 150+ = CRITICAL
        
        # Primary classification by RDS score
        if rds < 10:
            base_level = "LOW"
            base_color = "GREEN"
        elif rds < 30:
            base_level = "MODERATE"
            base_color = "YELLOW"
        elif rds < 80:
            base_level = "HIGH"
            base_color = "ORANGE"
        elif rds < 150:
            base_level = "VERY HIGH"
            base_color = "RED"
        else:
            base_level = "CRITICAL"
            base_color = "CRITICAL"
        
        # Generate message that makes sense: high RDS + low temp = cumulative past debt
        if rds > 50:
            # High RDS from past bad nights
            if consecutive_nights >= 3:
                if last_night_temp < RDS_NIGHTTIME_THRESHOLD:
                    return f"Recovery debt: {base_level} (RDS: {rds:.1f} from {consecutive_nights} consecutive hot nights - tonight cooler at {last_night_temp:.1f}C but cumulative sleep debt remains)", base_color
                else:
                    return f"Recovery debt: {base_level} (RDS: {rds:.1f} from {consecutive_nights} consecutive hot nights including tonight at {last_night_temp:.1f}C)", base_color
            elif consecutive_nights > 0:
                return f"Recovery debt: {base_level} (RDS: {rds:.1f} from {consecutive_nights} hot night(s) - tonight forecasted {last_night_temp:.1f}C)", base_color
            elif consecutive_nights == 0 and last_night_temp < RDS_NIGHTTIME_THRESHOLD:
                return f"Recovery debt: {base_level} (RDS: {rds:.1f} from recent hot nights - tonight forecasted {last_night_temp:.1f}C allows recovery, but past debt lingers due to exponential decay)", base_color
            else:
                return f"Recovery debt: {base_level} (RDS: {rds:.1f} from recent nights above 32C - tonight forecasted {last_night_temp:.1f}C)", base_color
        else:
            # Low-moderate RDS
            if last_night_temp < RDS_NIGHTTIME_THRESHOLD:
                return f"Recovery debt: {base_level} (outdoor temp {last_night_temp:.1f}C - most homes likely stayed below 32C threshold, RDS: {rds:.1f})", base_color
            elif last_night_temp < 34:
                return f"Recovery debt: {base_level} (outdoor temp {last_night_temp:.1f}C - if your home stayed above 32C, partial recovery failure, RDS: {rds:.1f})", base_color
            else:
                return f"Recovery debt: {base_level} (outdoor temp {last_night_temp:.1f}C - recovery may be impaired if your room stayed above 32C, RDS: {rds:.1f})", base_color
    
    def estimate_nighttime_temp_from_forecast(self, weather_forecast):
        """
        Estimate tonight's minimum temperature from forecast
        
        Args:
            weather_forecast: List of forecast data points
        
        Returns:
            Estimated nighttime minimum temperature
        """
        if not weather_forecast:
            return None
        
        # Find temperatures during night hours (10 PM - 6 AM local time)
        night_temps = []
        now = datetime.now()
        
        for item in weather_forecast:
            # Calculate hours from now
            time_diff = (item['timestamp'] - now).total_seconds() / 3600
            
            # Look at next 6-30 hours for tonight/tomorrow morning
            if 6 <= time_diff <= 30:
                hour = item['timestamp'].hour
                # Night hours: 10 PM to 6 AM
                if hour >= 22 or hour <= 6:
                    night_temps.append((item['timestamp'], item['temp']))
        
        if not night_temps:
            all_temps = [item['temp'] for item in weather_forecast[:8]]
            return min(all_temps) if all_temps else None

        return min(temp for _, temp in night_temps)

