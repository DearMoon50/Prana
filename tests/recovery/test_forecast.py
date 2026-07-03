from datetime import datetime, date, timedelta
from prana.recovery.forecast import (
    estimate_nighttime_conditions_from_forecast,
    select_night_date,
)


def _pt(ts, temp, humidity=None):
    return {"timestamp": ts, "temp": temp, "humidity": humidity}


def test_picks_coldest_future_night_hour():
    now = datetime(2026, 7, 2, 18, 0)
    fc = [
        _pt(now + timedelta(hours=7), 30.0, 60),   # 01:00 next day, night
        _pt(now + timedelta(hours=9), 27.0, 70),   # 03:00, colder night
        _pt(now + timedelta(hours=12), 33.0, 40),  # 06:00
    ]
    out = estimate_nighttime_conditions_from_forecast(fc, now=now)
    assert out["temp"] == 27.0
    assert out["humidity"] == 70


def test_discards_stale_points():
    now = datetime(2026, 7, 2, 18, 0)
    fc = [_pt(now - timedelta(hours=2), 10.0)]  # past
    assert estimate_nighttime_conditions_from_forecast(fc, now=now) is None


def test_skips_malformed_points():
    now = datetime(2026, 7, 2, 18, 0)
    fc = [
        {"timestamp": "not-a-datetime", "temp": 25.0},
        _pt(now + timedelta(hours=8), 26.0, 55),  # 02:00 night
    ]
    out = estimate_nighttime_conditions_from_forecast(fc, now=now)
    assert out["temp"] == 26.0


def test_empty_forecast_none():
    assert estimate_nighttime_conditions_from_forecast([], now=datetime(2026, 7, 2, 18, 0)) is None
    assert estimate_nighttime_conditions_from_forecast(None, now=datetime(2026, 7, 2, 18, 0)) is None


def test_night_date_before_midnight_is_today():
    # 22:00 -> the upcoming night is tonight (today's date)
    assert select_night_date(now=datetime(2026, 7, 2, 22, 0)) == date(2026, 7, 2)


def test_night_date_after_midnight_belongs_to_prior_evening():
    # 02:00 -> still "last night", label it the prior calendar day
    assert select_night_date(now=datetime(2026, 7, 3, 2, 0)) == date(2026, 7, 2)
