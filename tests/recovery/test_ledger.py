from prana.recovery.ledger import accumulate_debt
from prana.config import RECOVERY_DEBT_CAP_MIN


def _night(temp, humidity=None, hot_climate=False):
    return {"effective_temp": temp, "humidity": humidity, "hot_climate": hot_climate}


def test_all_cool_nights_zero_debt():
    nights = [_night(20.0) for _ in range(5)]
    assert accumulate_debt(nights) == 0.0


def test_single_hot_night_adds_its_loss():
    # one 30C night -> ~14 min debt (no prior debt to recover)
    debt = accumulate_debt([_night(30.0)])
    assert abs(debt - 14.0) < 0.5


def test_consecutive_hot_nights_accumulate():
    one = accumulate_debt([_night(33.0)])
    three = accumulate_debt([_night(33.0), _night(33.0), _night(33.0)])
    assert three > one


def test_cool_night_recovers_debt():
    # hot then cool: debt after cool night is lower than at its peak
    hot_only = accumulate_debt([_night(35.0), _night(35.0)])
    then_cool = accumulate_debt([_night(35.0), _night(35.0), _night(20.0)])
    assert then_cool < hot_only


def test_recovery_never_below_zero():
    nights = [_night(30.0)] + [_night(18.0) for _ in range(10)]
    assert accumulate_debt(nights) == 0.0


def test_debt_capped():
    nights = [_night(50.0) for _ in range(30)]
    assert accumulate_debt(nights) == RECOVERY_DEBT_CAP_MIN


def test_empty_is_zero():
    assert accumulate_debt([]) == 0.0
