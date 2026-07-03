"""Timezone-aware nighttime condition selection from a weather forecast.

Selection logic is unchanged from the legacy RDSCalculator method; the two fixes
are (1) an injectable `now` for deterministic tests, and (2) select_night_date,
which labels a post-midnight run with the evening the night began on, fixing the
datetime.now().date() bug that mislabelled early-morning runs.
"""
import math
from datetime import datetime, date, timedelta
from typing import Optional
from backend.logger import get_logger

_log = get_logger("recovery.forecast")


def select_night_date(now=None) -> date:
    """Calendar date the current/upcoming night belongs to.

    A run at 02:00 is still 'last night' -> label it the previous day. A run at or
    after ~18:00 (or any time before midnight) belongs to today.
    """
    if now is None:
        now = datetime.now()
    if now.hour < 12:
        return (now - timedelta(days=1)).date()
    return now.date()


def estimate_nighttime_conditions_from_forecast(weather_forecast, now=None) -> Optional[dict]:
    """Coldest valid future night hour (22:00-06:00, 6-30h ahead) + its humidity.

    Returns {'temp': float, 'humidity': float|None} or None if no valid future
    data. Malformed and stale points are discarded.
    """
    if not weather_forecast:
        return None
    if now is None:
        now = datetime.now()

    valid_items = []
    malformed = 0
    for item in weather_forecast:
        ts = item.get('timestamp')
        temp = item.get('temp')
        if not isinstance(ts, datetime) or temp is None:
            malformed += 1
            continue
        try:
            temp = float(temp)
        except (TypeError, ValueError):
            malformed += 1
            continue
        if not math.isfinite(temp):
            malformed += 1
            continue
        valid_items.append({'timestamp': ts, 'temp': temp, 'humidity': item.get('humidity')})

    if malformed:
        _log.warning("Discarded %d malformed forecast points (bad timestamp or temp)", malformed)
    if not valid_items:
        _log.error("No well-formed forecast points available")
        return None

    night_points = []
    stale_count = 0
    for item in valid_items:
        if item['timestamp'] <= now:
            stale_count += 1
            continue
        time_diff = (item['timestamp'] - now).total_seconds() / 3600
        if 6 <= time_diff <= 30:
            hour = item['timestamp'].hour
            if hour >= 22 or hour <= 6:
                night_points.append((item['timestamp'], item['temp'], item.get('humidity')))

    if stale_count > 0:
        _log.warning("Discarded %d stale forecast points (timestamps in the past)", stale_count)

    if not night_points:
        valid_future = [item for item in valid_items if item['timestamp'] > now]
        if not valid_future:
            _log.error("All forecast timestamps stale - no valid future data available")
            return None
        fallback = valid_future[:8]
        coldest = min(fallback, key=lambda x: x['temp'])
        return {'temp': coldest['temp'], 'humidity': coldest.get('humidity')}

    _, min_temp, min_humidity = min(night_points, key=lambda x: x[1])
    return {'temp': min_temp, 'humidity': min_humidity}
