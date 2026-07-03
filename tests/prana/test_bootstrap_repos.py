from framework.persistence.sqlite import SQLiteRDSStateRepository, SQLiteRiskEvalRepository
from prana.bot.bootstrap import build_rds_repo, build_risk_eval_repo


def test_build_rds_repo_returns_rds_state_repo():
    assert isinstance(build_rds_repo(), SQLiteRDSStateRepository)


def test_build_risk_eval_repo_returns_risk_eval_repo():
    assert isinstance(build_risk_eval_repo(), SQLiteRiskEvalRepository)