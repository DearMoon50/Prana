from prana.ccri_calculator import CCRICalculator
from prana.config import RECOVERY_DEBT_CAP_MIN


def test_to_ccri_recovery_score_maps_minutes_to_0_100():
    c = CCRICalculator()
    assert c.to_ccri_recovery_score(0.0) == 0.0
    assert c.to_ccri_recovery_score(RECOVERY_DEBT_CAP_MIN) == 100.0
    assert c.to_ccri_recovery_score(RECOVERY_DEBT_CAP_MIN / 2) == 50.0


def test_existing_recovery_score_still_clamps():
    c = CCRICalculator()
    assert c.calculate_recovery_score(150) == 100
    assert c.calculate_recovery_score(-5) == 0
