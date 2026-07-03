"""Wires framework components for PRANA's bot at startup."""
from __future__ import annotations

from framework.ai.factory import build_provider
from framework.config.settings import FrameworkSettings
from framework.messaging.registry import MessagingRegistry
from framework.messaging.whatsapp import TwilioWhatsAppChannel
from framework.persistence.sqlite import (
    SQLiteUserRepository, SQLiteCheckinRepository,
    SQLiteRDSStateRepository, SQLiteRiskEvalRepository,
    SQLiteHouseholdRepository,
)
from framework.tools.base import ToolRegistry
from framework.context.user import UserContext
from prana.ai_tools.risk import risk_tool
from prana.ai_tools.checkin import record_checkin_tool
from prana.config import DATABASE_URL
from prana.bot.commands import CommandRegistry, handle_help, handle_risk, handle_profile

settings = FrameworkSettings()


_cache = {}

def build_registry() -> ToolRegistry:
    if "registry" not in _cache:
        reg = ToolRegistry()
        reg.register(risk_tool)
        reg.register(record_checkin_tool)
        _cache["registry"] = reg
    return _cache["registry"]


def build_provider_chain():
    if "provider" not in _cache:
        _cache["provider"] = build_provider(settings)
    return _cache["provider"]


def build_messaging() -> MessagingRegistry:
    if "messaging" not in _cache:
        reg = MessagingRegistry()
        reg.add(TwilioWhatsAppChannel(
            settings.whatsapp_account_sid, settings.whatsapp_auth_token, settings.whatsapp_from_number,
        ))
        _cache["messaging"] = reg
    return _cache["messaging"]


def build_repo() -> SQLiteUserRepository:
    if "user_repo" not in _cache:
        _cache["user_repo"] = SQLiteUserRepository(DATABASE_URL)
    return _cache["user_repo"]


def build_checkin_repo() -> SQLiteCheckinRepository:
    if "checkin_repo" not in _cache:
        _cache["checkin_repo"] = SQLiteCheckinRepository(DATABASE_URL)
    return _cache["checkin_repo"]


def build_rds_repo() -> SQLiteRDSStateRepository:
    if "rds_repo" not in _cache:
        from prana.config import RECOVERY_WINDOW_NIGHTS
        _cache["rds_repo"] = SQLiteRDSStateRepository(DATABASE_URL, max_days=RECOVERY_WINDOW_NIGHTS)
    return _cache["rds_repo"]


def build_risk_eval_repo() -> SQLiteRiskEvalRepository:
    if "risk_eval_repo" not in _cache:
        _cache["risk_eval_repo"] = SQLiteRiskEvalRepository(DATABASE_URL)
    return _cache["risk_eval_repo"]


def build_household_repo() -> SQLiteHouseholdRepository:
    if "household_repo" not in _cache:
        _cache["household_repo"] = SQLiteHouseholdRepository(DATABASE_URL)
    return _cache["household_repo"]


def build_commands() -> CommandRegistry:
    cmd_reg = CommandRegistry(prefix="/")
    cmd_reg.register("help", "List all available commands.", lambda ctx: handle_help_dispatch(cmd_reg, ctx))
    cmd_reg.register("risk", "Quickly check your current climate risk scores.", handle_risk)
    cmd_reg.register("profile", "View your registered home profile.", handle_profile)
    return cmd_reg


async def handle_help_dispatch(reg: CommandRegistry, ctx: UserContext) -> str:
    return reg.get_help_text()
