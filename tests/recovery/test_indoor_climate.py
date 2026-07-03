from prana.recovery import indoor_climate as ic


def test_ashrae_ac_offset_is_temp_dependent_and_near_minus_3_5_at_30():
    off = ic.ashrae_ac_offset(30.0)
    assert -3.7 < off < -3.3, off
    # widens (more cooling) with heat
    assert ic.ashrae_ac_offset(35.0) < ic.ashrae_ac_offset(30.0)


def test_no_onboarding_is_zero_offset():
    assert ic.compute_onboarding_temp_offset(None) == 0.0
    assert ic.compute_onboarding_temp_offset({}) == 0.0


def test_ac_uses_ashrae_curve_not_flat_minus_3():
    # AC home at 30C outdoor should get the ASHRAE ~-3.5, not the old flat -3.0
    off = ic.compute_onboarding_temp_offset({"ac": True}, outdoor_temp=30.0)
    assert abs(off - ic.ashrae_ac_offset(30.0)) < 0.01


def test_structural_cooling_capped_at_minus_4():
    # tin roof + top floor + AC + windows in hot_dry, cool night: still >= -4.0
    off = ic.compute_onboarding_temp_offset(
        {"ac": True, "windows_open": True, "roof_material": "tin", "floor_level": "top"},
        outdoor_temp=22.0, climate_zone="hot_dry",
    )
    assert off >= -4.0


def test_band_width_widens_with_ac():
    from prana.config import RDS_INDOOR_OFFSET_BAND_WIDTH, RDS_AC_EXTRA_BAND_WIDTH
    assert ic.compute_band_width({}) == RDS_INDOOR_OFFSET_BAND_WIDTH
    assert ic.compute_band_width({"ac": True}) == RDS_INDOOR_OFFSET_BAND_WIDTH + RDS_AC_EXTRA_BAND_WIDTH


def test_effective_indoor_temp():
    assert ic.effective_indoor_temp(30.0, -3.5) == 26.5
