from framework.persistence.sqlite import SQLiteRDSStateRepository, SQLiteRiskEvalRepository
from prana.bot.bootstrap import build_rds_repo, build_risk_eval_repo
from prana.config import RECOVERY_WINDOW_NIGHTS


def test_build_rds_repo_returns_rds_state_repo():
    assert isinstance(build_rds_repo(), SQLiteRDSStateRepository)


def test_build_rds_repo_uses_recovery_window_nights():
    # Regression guard: build_rds_repo() previously wired the retired
    # RDS_MAX_DAYS(4) constant instead of the ledger's RECOVERY_WINDOW_NIGHTS(7),
    # silently truncating every persisted user's history to 4 nights.
    assert build_rds_repo().max_days == RECOVERY_WINDOW_NIGHTS


def test_build_risk_eval_repo_returns_risk_eval_repo():
    assert isinstance(build_risk_eval_repo(), SQLiteRiskEvalRepository)