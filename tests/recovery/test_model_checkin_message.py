from datetime import date, timedelta
from prana.recovery.model import RecoveryModel
from prana.config import RECOVERY_PER_COOL_NIGHT_MIN


def _hot_model():
    m = RecoveryModel()
    for i, t in enumerate([35, 36, 34]):
        m.add_night_temperature(t, date=date(2026, 7, 1) + timedelta(days=i))
    return m


def test_no_checkin_is_noop():
    m = _hot_model()
    rds = m.calculate_rds()
    out, meta = m.apply_sleep_checkin_adjustment(rds, None)
    assert meta["applied"] is False
    assert out["debt_minutes_mid"] == rds["debt_minutes_mid"]


def test_bad_checkin_bounded_by_one_night_budget():
    m = _hot_model()
    rds = m.calculate_rds()
    out, meta = m.apply_sleep_checkin_adjustment(
        rds, {"sleep_quality": "poor", "power_issue": True, "cooling_issue": True})
    delta = out["debt_minutes_mid"] - rds["debt_minutes_mid"]
    assert 0 < delta <= RECOVERY_PER_COOL_NIGHT_MIN + 1e-6


def test_good_checkin_reduces_debt_not_below_zero():
    m = _hot_model()
    rds = m.calculate_rds()
    out, _ = m.apply_sleep_checkin_adjustment(rds, {"sleep_quality": "good"})
    assert out["debt_minutes_mid"] <= rds["debt_minutes_mid"]
    assert out["debt_minutes_mid"] >= 0.0


def test_checkin_preserves_keys():
    m = _hot_model()
    rds = m.calculate_rds()
    out, _ = m.apply_sleep_checkin_adjustment(rds, {"sleep_quality": "poor"})
    for k in ("rds_mid", "debt_minutes_mid", "tier", "personalized", "consecutive_nights"):
        assert k in out


def test_message_mentions_minutes_and_returns_color():
    m = _hot_model()
    rds = m.calculate_rds()
    msg, color = m.get_rds_message(rds)
    assert "min" in msg.lower()
    assert color in {"GREEN", "YELLOW", "ORANGE", "RED"}


def test_confidence_levels():
    m = RecoveryModel()
    assert m.estimate_recovery_confidence({"sleep_quality": "good"}) == "HIGH"
    assert m.estimate_recovery_confidence() == "LOW"
