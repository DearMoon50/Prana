from prana import config


def test_sleep_loss_anchors_are_monotonic_nonneg():
    anchors = config.SLEEP_LOSS_ANCHORS
    temps = [t for t, _ in anchors]
    losses = [m for _, m in anchors]
    assert temps == sorted(temps), "anchor temps must be ascending"
    assert losses == sorted(losses), "minutes-lost must be non-decreasing"
    assert losses[0] == 0.0
    assert all(m >= 0 for m in losses)


def test_ledger_constants_present_and_sane():
    assert config.RECOVERY_DEBT_CAP_MIN == 240
    assert config.RECOVERY_PER_COOL_NIGHT_MIN == 14
    assert config.RECOVERY_WINDOW_NIGHTS == 7
    assert config.HOT_CLIMATE_SLEEP_MULTIPLIER == 1.0
    # tiers strictly ascending and below the cap
    assert 0 < config.RECOVERY_TIER_MODERATE_MIN < config.RECOVERY_TIER_HIGH_MIN \
        < config.RECOVERY_TIER_SEVERE_MIN <= config.RECOVERY_DEBT_CAP_MIN


def test_ashrae_ac_offset_constants_present():
    # temp-dependent AC offset replacing the flat -3.0
    assert config.RDS_ASHRAE_AC_BASELINE == -1.5
    assert config.RDS_ASHRAE_AC_INTERACTION < 0
